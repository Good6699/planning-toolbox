"""Domain service for migrating Unity prefab Atlas sprite references."""

from __future__ import annotations

import codecs
import copy
import datetime as _datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
from collections import Counter, defaultdict


_GUID_RE = re.compile(r"(?m)^guid:\s*([0-9a-fA-F]+)\s*$")
_FIRST_SECOND_RE = re.compile(
    r"-\s*first:\s*\r?\n\s*213:\s*(-?\d+)\s*\r?\n\s*second:\s*([^\r\n]+)"
)
_FIELD_LINE_RE = re.compile(
    rb"(?m)^(?P<indent>[ \t]*)m_Sprite:(?P<space>[ \t]*)\{(?P<body>[^}\r\n]*)\}(?P<trail>[^\r\n]*)"
)
_FILE_ID_BYTES_RE = re.compile(rb"(?<![A-Za-z0-9_])fileID(?P<sep>\s*:\s*)(?P<value>-?\d+)")
_GUID_BYTES_RE = re.compile(rb"(?<![A-Za-z0-9_])guid(?P<sep>\s*:\s*)(?P<value>[0-9a-fA-F]+)")
_PREFIX_RE = re.compile(r"^(H?)(\d+)_", re.IGNORECASE)
_VALID_GUID_RE = re.compile(r"^[0-9a-fA-F]+$")
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *("COM%d" % i for i in range(1, 10)),
    *("LPT%d" % i for i in range(1, 10)),
}


class AtlasMigrationError(ValueError):
    """A user-correctable Atlas migration error."""


def _stable_id(prefix, value):
    digest = hashlib.sha256(os.path.normcase(value).encode("utf-8")).hexdigest()[:20]
    return "%s_%s" % (prefix, digest)


def _inside(path, root):
    path = os.path.normcase(os.path.realpath(path))
    root = os.path.normcase(os.path.realpath(root))
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _clean_yaml_name(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _parse_indented_table(text, table_name, key_is_number):
    lines = text.splitlines()
    values = []
    header = re.compile(r"^(\s*)%s:\s*$" % re.escape(table_name))
    entry = re.compile(r"^\s*(.+?):\s*(-?\d+)\s*$")
    numeric_entry = re.compile(r"^\s*(-?\d+):\s*(.+?)\s*$")
    index = 0
    while index < len(lines):
        found = header.match(lines[index])
        if not found:
            index += 1
            continue
        indent = len(found.group(1).expandtabs(8))
        index += 1
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            current_indent = len(line) - len(line.lstrip(" \t"))
            if current_indent <= indent:
                break
            match = numeric_entry.match(line) if key_is_number else entry.match(line)
            if match:
                if key_is_number:
                    file_id, name = int(match.group(1)), _clean_yaml_name(match.group(2))
                else:
                    name, file_id = _clean_yaml_name(match.group(1)), int(match.group(2))
                if name:
                    values.append((file_id, name))
            index += 1
    return values


def _parse_meta(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as stream:
        text = stream.read()
    guid_match = _GUID_RE.search(text)
    guid = guid_match.group(1).lower() if guid_match else ""
    pairs = []
    for match in _FIRST_SECOND_RE.finditer(text):
        pairs.append((int(match.group(1)), _clean_yaml_name(match.group(2))))
    pairs.extend(_parse_indented_table(text, "fileIDToRecycleName", True))
    pairs.extend(_parse_indented_table(text, "nameFileIdTable", False))
    unique = []
    seen = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return guid, unique


def _meta_group_tokens(meta_path, atlas_root):
    rel = os.path.relpath(meta_path, atlas_root).replace("\\", "/")
    if rel.lower().endswith(".meta"):
        rel = rel[:-5]
    stem = os.path.basename(rel)
    if "." in stem:
        stem = stem.split(".", 1)[0]
    parent = os.path.dirname(rel).replace("\\", "/").strip("/")
    tokens = {stem.casefold()}
    if parent:
        tokens.add(parent.casefold())
        tokens.add((parent + "/" + stem).casefold())
        tokens.add(os.path.basename(parent).casefold())
    return sorted(token for token in tokens if token)


def _scan_atlas(atlas_root):
    records = []
    by_guid = defaultdict(list)
    if not os.path.isdir(atlas_root):
        return {"records": records, "by_guid": by_guid}
    for current, dirs, files in os.walk(atlas_root, followlinks=False):
        dirs.sort(key=str.casefold)
        for filename in sorted(files, key=str.casefold):
            if not filename.lower().endswith(".meta"):
                continue
            path = os.path.join(current, filename)
            if not _inside(path, atlas_root):
                continue
            guid, pairs = _parse_meta(path)
            if not guid or not pairs:
                continue
            record = {
                "path": path,
                "guid": guid,
                "pairs": pairs,
                "tokens": _meta_group_tokens(path, atlas_root),
            }
            records.append(record)
            by_guid[guid].append(record)
    return {"records": records, "by_guid": by_guid}


def _build_atlas_catalog(atlas_root, index=None):
    atlas_index = index if index is not None else _scan_atlas(atlas_root)
    duplicate_guids = {
        guid for guid, records in atlas_index["by_guid"].items() if len(records) > 1
    }
    atlases = {}
    for record in atlas_index["records"]:
        atlas_id = _stable_id("atx", record["path"])
        rel = os.path.relpath(record["path"], atlas_root).replace("\\", "/")
        stem = os.path.basename(rel)
        if stem.lower().endswith(".meta"):
            stem = stem[:-5]
        if "." in stem:
            stem = stem.split(".", 1)[0]
        excluded = record["guid"] in duplicate_guids
        by_file_id = defaultdict(set)
        by_name = defaultdict(set)
        for file_id, name in record["pairs"]:
            by_file_id[file_id].add(name)
            by_name[name].add(file_id)
        sprites = []
        ambiguous = 0
        for file_id, name in sorted(record["pairs"], key=lambda item: (item[1].casefold(), item[0])):
            if excluded:
                ambiguous += 1
                continue
            if len(by_file_id[file_id]) > 1 or len(by_name[name]) > 1:
                ambiguous += 1
                continue
            sprites.append({
                "id": _stable_id("spr", "%s|%s|%s" % (record["path"], file_id, name)),
                "name": name,
                "file_id": file_id,
            })
        atlases[atlas_id] = {
            "id": atlas_id,
            "path": record["path"],
            "relative_path": rel,
            "name": stem,
            "guid": record["guid"],
            "sprites": sprites,
            "status": "excluded" if excluded else "ready",
            "error": "重复 GUID" if excluded else ("歧义映射 %d 项" % ambiguous if ambiguous else ""),
        }
    return atlases


def _parse_prefab_bytes(data):
    references = defaultdict(int)
    lines = []
    for match in _FIELD_LINE_RE.finditer(data):
        body = match.group("body")
        file_match = _FILE_ID_BYTES_RE.search(body)
        guid_match = _GUID_BYTES_RE.search(body)
        if not file_match or not guid_match:
            continue
        file_id = int(file_match.group("value"))
        guid = guid_match.group("value").decode("ascii").lower()
        if file_id == 0 or not guid or set(guid) == {"0"}:
            continue
        key = (guid, file_id)
        references[key] += 1
        lines.append((match.start(), match.end(), key))
    return references, lines


def _target_prefix_name(source_name, target_group_name):
    target_number = re.search(r"(\d+)(?!.*\d)", target_group_name)
    source_prefix = _PREFIX_RE.match(source_name)
    if not target_number or not source_prefix:
        return source_name
    return "%s%s_%s" % (
        source_prefix.group(1), target_number.group(0), source_name[source_prefix.end():]
    )


def _validate_basename(name):
    if not isinstance(name, str) or not name:
        raise AtlasMigrationError("目标名称不能为空")
    if name != name.strip() or name.endswith((".", " ")):
        raise AtlasMigrationError("目标名称不能以点或空格结尾")
    if os.path.basename(name) != name or "/" in name or "\\" in name:
        raise AtlasMigrationError("目标名称不能包含路径分隔符")
    if name.lower().endswith((".png", ".meta")):
        raise AtlasMigrationError("目标名称不能包含扩展名")
    if any(ord(char) < 32 or char in '<>:"|?*' for char in name):
        raise AtlasMigrationError("目标名称包含非法字符")
    if name.split(".", 1)[0].upper() in _RESERVED_NAMES:
        raise AtlasMigrationError("目标名称是 Windows 保留名")
    return name


def _log(log, message):
    if log is not None:
        log(message)


class AtlasMigrationService:
    """Persistent, standard-library-only Atlas migration domain service."""

    def __init__(self, drafts_dir=None):
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        self.drafts_dir = os.path.realpath(
            drafts_dir or os.path.join(appdata, "planning-toolbox", "atlas-migration-drafts")
        )
        os.makedirs(self.drafts_dir, exist_ok=True)
        self._locks_guard = threading.Lock()
        self._locks = {}

    def list_drafts(self):
        views = []
        for filename in sorted(os.listdir(self.drafts_dir), key=str.casefold):
            if not filename.endswith(".json"):
                continue
            try:
                draft = self._load(filename[:-5])
                views.append({
                    "id": draft["id"],
                    "created_at": draft["created_at"],
                    "updated_at": draft["updated_at"],
                    "stage": draft["stage"],
                })
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        views.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return views

    def get_draft(self, draft_id):
        with self._lock(draft_id):
            return self._view(self._load(draft_id))

    def create_draft(self, paths):
        if not isinstance(paths, (list, tuple)) or not paths:
            raise AtlasMigrationError("请选择至少一个预制目录")
        context = self._validate_paths(paths)
        atlas_index = _scan_atlas(context["atlas_root"])
        groups = self._scan_groups(context["game_ui_root"])
        image_index = self._scan_source_images(context["game_ui_root"])
        prefabs = []
        images = {}
        diagnostics = []
        seen_prefabs = set()
        for selected in context["selected_roots"]:
            for current, dirs, files in os.walk(selected, followlinks=False):
                dirs.sort(key=str.casefold)
                for filename in sorted(files, key=str.casefold):
                    if not filename.lower().endswith(".prefab"):
                        continue
                    path = os.path.realpath(os.path.join(current, filename))
                    if path in seen_prefabs:
                        continue
                    if not _inside(path, context["prefab_root"]) or not _inside(path, selected):
                        diagnostics.append("跳过越界预制: %s" % path)
                        continue
                    seen_prefabs.add(path)
                    prefab = self._scan_prefab(
                        path, context, atlas_index, groups, images, image_index
                    )
                    prefabs.append(prefab)
        prefabs.sort(key=lambda item: (-item["source_group_count"], item["relative_path"].casefold()))
        draft_id = secrets.token_hex(16)
        now = _datetime.datetime.now().isoformat(timespec="seconds")
        draft = {
            "version": 2,
            "id": draft_id,
            "created_at": now,
            "updated_at": now,
            "stage": "planning",
            "project_root": context["project_root"],
            "input_root": context["input_root"],
            "prefab_root": context["prefab_root"],
            "atlas_root": context["atlas_root"],
            "game_ui_root": context["game_ui_root"],
            "prefabs": prefabs,
            "images": images,
            "groups": groups,
            "atlases": _build_atlas_catalog(context["atlas_root"], atlas_index),
            "plans": {},
            "copies": {},
            "completed_plans": [],
            "diagnostics": diagnostics,
            "txt_path": "",
        }
        self._save(draft)
        return self._view(draft)

    def plan_groups(self, draft_id, prefab_id, source_group_ids, target_group_id):
        if not isinstance(source_group_ids, (list, tuple)) or not source_group_ids:
            raise AtlasMigrationError("请选择至少一个源图集组")
        with self._lock(draft_id):
            draft = self._load(draft_id)
            self._require_plannable(draft)
            prefab = self._prefab(draft, prefab_id)
            target_group = self._group(draft, target_group_id)
            wanted = set(source_group_ids)
            if target_group["id"] in wanted:
                raise AtlasMigrationError("目标图集组不能是当前源图集组")
            source_image_ids = list(dict.fromkeys(
                reference["source_image_id"]
                for reference in prefab["references"]
                if reference.get("source_group_id") in wanted
                and reference.get("source_image_id")
            ))
            manual_locked = {
                reference.get("source_image_id")
                for reference in prefab["references"]
                if reference.get("source_image_id")
                and self._plan_for_reference(draft, prefab_id, reference["id"])
                and self._plan_for_reference(draft, prefab_id, reference["id"]).get("kind") == "manual"
            }
            source_image_ids = [item for item in source_image_ids if item not in manual_locked]
            if not source_image_ids:
                raise AtlasMigrationError("选中的源组没有可批量规划的图片")
            for source_image_id in source_image_ids:
                existing = self._plan_for(draft, prefab_id, source_image_id)
                if existing and draft["copies"][existing["copy_id"]].get("status") == "success":
                    raise AtlasMigrationError("已复制的资源不能修改迁移目标")
            for source_image_id in source_image_ids:
                self._add_plan(
                    draft, prefab_id, source_image_id, target_group_id, "group",
                    refresh=False,
                )
            self._refresh_conflicts(draft)
            self._refresh_stage(draft)
            self._save(draft)
            return self._view(draft)

    def add_manual_group(self, draft_id, prefab_id, group_id):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            self._require_plannable(draft)
            prefab = self._prefab(draft, prefab_id)
            self._group(draft, group_id)
            manual_ids = prefab.setdefault("manual_group_ids", [])
            if group_id not in manual_ids:
                manual_ids.append(group_id)
            self._save(draft)
            return self._view(draft)

    def plan_manual_reference(self, draft_id, prefab_id, reference_id, target_sprite_id):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            self._require_plannable(draft)
            prefab = self._prefab(draft, prefab_id)
            reference = next(
                (item for item in prefab["references"] if item["id"] == reference_id), None
            )
            if not reference:
                raise AtlasMigrationError("引用 ID 无效")
            if reference.get("status") != "ready":
                raise AtlasMigrationError("仅已解析的资源可以手动指定")
            target_sprite = None
            target_atlas = None
            for atlas in draft["atlases"].values():
                if atlas.get("status") != "ready":
                    continue
                for sprite in atlas.get("sprites", []):
                    if sprite["id"] == target_sprite_id:
                        target_sprite, target_atlas = sprite, atlas
                        break
                if target_sprite:
                    break
            if not target_sprite or not target_atlas:
                raise AtlasMigrationError("目标 Sprite 不存在或不可选")
            old = (reference["guid"], reference["file_id"])
            new = (target_atlas["guid"], target_sprite["file_id"])
            if old == new:
                raise AtlasMigrationError("目标与当前引用相同")
            existing = self._plan_for_reference(draft, prefab_id, reference_id)
            if existing:
                if existing.get("kind") == "manual":
                    if existing.get("rewrite", {}).get("status") == "success":
                        raise AtlasMigrationError("已修改的引用不能重新指定")
                else:
                    if draft["copies"][existing["copy_id"]].get("status") == "success":
                        raise AtlasMigrationError("已复制的资源不能改为手动指定")
                self._unlink_plan(draft, existing["id"])
            plan_id = _stable_id("pln", "%s|%s|manual" % (prefab_id, reference_id))
            draft["plans"][plan_id] = {
                "id": plan_id,
                "prefab_id": prefab_id,
                "kind": "manual",
                "origin": "manual",
                "reference_ids": [reference_id],
                "target_atlas_id": target_atlas["id"],
                "target_sprite_name": target_sprite["name"],
                "resolution": {"status": "success", "guid": new[0], "file_id": new[1], "error": ""},
                "rewrite": {"status": "pending", "error": ""},
            }
            self._refresh_stage(draft)
            self._save(draft)
            return self._view(draft)

    def rename_plan(self, draft_id, plan_id, target_name):
        target_name = _validate_basename(target_name)
        with self._lock(draft_id):
            draft = self._load(draft_id)
            self._require_plannable(draft)
            plan = self._plan(draft, plan_id)
            if plan.get("kind") == "manual":
                raise AtlasMigrationError("手动指定的计划不能修改目标名称")
            copy_item = draft["copies"][plan["copy_id"]]
            if copy_item.get("status") == "success":
                raise AtlasMigrationError("已复制的资源不能改名")
            copy_item["target_name"] = target_name
            copy_item["manual_name"] = True
            self._refresh_conflicts(draft)
            self._save(draft)
            return self._view(draft)

    def remove_plan(self, draft_id, plan_id):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            self._require_plannable(draft)
            plan = self._plan(draft, plan_id)
            if plan.get("kind") == "manual":
                if plan.get("rewrite", {}).get("status") == "success":
                    raise AtlasMigrationError("已修改的引用不能移除计划")
                del draft["plans"][plan_id]
            else:
                if draft["copies"][plan["copy_id"]].get("status") == "success":
                    raise AtlasMigrationError("已复制的资源不能移除迁移计划")
                self._unlink_plan(draft, plan_id)
            self._refresh_conflicts(draft)
            self._refresh_stage(draft)
            self._save(draft)
            return self._view(draft)

    def discard(self, draft_id):
        with self._lock(draft_id):
            path = self._draft_path(draft_id)
            if not os.path.isfile(path):
                raise AtlasMigrationError("草稿不存在")
            os.unlink(path)
        return {"id": draft_id, "discarded": True}

    def copy_files(self, draft_id, log=None):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            pending = [
                plan for plan in draft["plans"].values()
                if plan.get("copy_id")
                and draft["copies"][plan["copy_id"]].get("status") != "success"
            ]
            if not pending:
                raise AtlasMigrationError("没有需要复制的迁移计划")
            self._refresh_conflicts(draft)
            conflicts = [item for item in draft["copies"].values() if item.get("conflict")]
            if conflicts:
                self._save(draft)
                raise AtlasMigrationError("存在手动重名冲突，复制已阻止")
            for item in draft["copies"].values():
                if item.get("status") == "success":
                    continue
                try:
                    self._validate_draft(draft)
                    self._copy_pair(item)
                    item["status"] = "success"
                    item["error"] = ""
                    _log(log, "复制成功: %s.png" % item["target_name"])
                except Exception as exc:
                    item["status"] = "failed"
                    item["error"] = str(exc)
                    _log(log, "复制失败: %s (%s)" % (item["target_name"], exc))
                self._save(draft)
            statuses = [item.get("status") for item in draft["copies"].values()]
            draft["stage"] = "copied" if statuses and all(x == "success" for x in statuses) else "copy_partial"
            self._save(draft)
            return self._view(draft)

    def resolve_final(self, draft_id, log=None):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            if draft["stage"] not in ("copied", "resolution_partial", "resolved", "rewrite_partial"):
                raise AtlasMigrationError("请先完成资源复制")
            atlas_index = _scan_atlas(draft["atlas_root"])
            for plan in draft["plans"].values():
                plan.setdefault("rewrite", {"status": "pending", "error": ""})
                if plan.get("kind") == "manual":
                    continue
                if plan["rewrite"].get("status") == "success":
                    continue
                copy_item = draft["copies"][plan["copy_id"]]
                if copy_item.get("status") != "success":
                    plan["resolution"] = {"status": "failed", "error": "资源尚未复制"}
                    continue
                matches = self._find_final_matches(
                    atlas_index, self._group(draft, plan["target_group_id"]), copy_item["target_name"]
                )
                if len(matches) == 1:
                    guid, file_id = matches[0]
                    plan["resolution"] = {
                        "status": "success", "guid": guid, "file_id": file_id, "error": ""
                    }
                    _log(log, "解析成功: %s -> %s/%s" % (copy_item["target_name"], guid, file_id))
                else:
                    reason = "未在最终 Atlas 找到" if not matches else "最终 Atlas 映射不唯一"
                    plan["resolution"] = {"status": "failed", "error": reason}
                    _log(log, "解析失败: %s (%s)" % (copy_item["target_name"], reason))
                self._save(draft)
            remaining = [
                item for item in draft["plans"].values()
                if item.get("rewrite", {}).get("status") != "success"
            ]
            draft["stage"] = (
                "resolved" if remaining and all(
                    item.get("resolution", {}).get("status") == "success" for item in remaining
                ) else "resolution_partial"
            )
            self._save(draft)
            return self._view(draft)

    def rewrite_prefabs(self, draft_id, log=None):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            plans = list(draft["plans"].values())
            pending_any = any(
                item.get("resolution", {}).get("status") == "success"
                and item.get("rewrite", {}).get("status") != "success"
                for item in plans
            )
            all_done = (
                bool(draft.get("completed_plans"))
                and all(
                    item.get("rewrite", {}).get("status") == "success" for item in plans
                )
            )
            if not pending_any and not all_done:
                raise AtlasMigrationError("没有已解析且待修改的计划")
            if not draft.get("txt_path"):
                report_time = _datetime.datetime.now()
                while True:
                    stamp = report_time.strftime("%Y%m%d_%H%M%S")
                    report_path = os.path.join(
                        draft["input_root"], "图集引用迁移_%s.txt" % stamp
                    )
                    if not os.path.exists(report_path):
                        draft["txt_path"] = report_path
                        break
                    report_time += _datetime.timedelta(seconds=1)
            for plan in draft["plans"].values():
                plan.setdefault("rewrite", {"status": "pending", "error": ""})
            self._verify_manual_targets(draft, log)
            self._refresh_stage(draft)
            for prefab in draft["prefabs"]:
                plans = [item for item in draft["plans"].values() if item["prefab_id"] == prefab["id"]]
                eligible = [
                    item for item in plans
                    if item.get("resolution", {}).get("status") == "success"
                    and item["rewrite"].get("status") != "success"
                ]
                if eligible:
                    try:
                        self._rewrite_one(draft, prefab, eligible)
                        for plan in eligible:
                            plan["rewrite"] = {"status": "success", "error": ""}
                            plan["source_snapshot"] = self._source_snapshot(draft, prefab, plan)
                        _log(log, "预制修改成功: %s" % prefab["relative_path"])
                    except Exception as exc:
                        for plan in eligible:
                            plan["rewrite"] = {"status": "failed", "error": str(exc)}
                        _log(log, "预制修改跳过: %s (%s)" % (prefab["relative_path"], exc))
                self._refresh_prefab_rewrite(prefab, plans)
                self._save(draft)
            self._revalidate_rewrites(draft, log)
            self._archive_completed_plans(draft)
            self._refresh_prefab_references(draft)
            self._save(draft)
            complete = (
                bool(draft.get("completed_plans"))
                and not draft["plans"]
            )
            draft["stage"] = "completed" if complete else "rewrite_partial"
            self._save(draft)
            if complete:
                self._write_report(draft)
            result = self._view(draft)
            if complete:
                os.unlink(self._draft_path(draft_id))
            return result

    def _validate_paths(self, paths):
        selected = []
        context = None
        for value in paths:
            if not isinstance(value, str) or not os.path.isdir(value):
                raise AtlasMigrationError("输入必须是存在的文件夹")
            path = os.path.realpath(value)
            current = path
            prefab_root = ""
            while True:
                parts = []
                probe = current
                for _ in range(5):
                    parts.append(os.path.basename(probe).casefold())
                    probe = os.path.dirname(probe)
                if parts == ["prefabs", "ui", "resources", "assets", "client"]:
                    prefab_root = current
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent
            if not prefab_root or not _inside(path, prefab_root):
                raise AtlasMigrationError("输入目录必须位于 Client\\Assets\\Resources\\UI\\Prefabs 内")
            client_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(prefab_root))))
            project_root = os.path.dirname(client_root)
            candidate = {
                "project_root": project_root,
                "prefab_root": prefab_root,
                "atlas_root": os.path.join(client_root, "Assets", "Resources", "UI", "Atlas"),
                "game_ui_root": os.path.join(client_root, "Assets", "GameAssets", "UI"),
            }
            if not os.path.isdir(candidate["atlas_root"]) or not os.path.isdir(candidate["game_ui_root"]):
                raise AtlasMigrationError("工程缺少 Atlas 或 GameAssets\\UI 目录")
            if context and os.path.normcase(candidate["project_root"]) != os.path.normcase(context["project_root"]):
                raise AtlasMigrationError("所有输入目录必须属于同一工程")
            context = candidate
            selected.append(path)
        context["selected_roots"] = sorted(set(selected), key=str.casefold)
        try:
            context["input_root"] = os.path.commonpath(context["selected_roots"])
        except ValueError:
            raise AtlasMigrationError("输入目录不属于同一工程")
        if not _inside(context["input_root"], context["prefab_root"]):
            raise AtlasMigrationError("输入目录越界")
        return context

    def _scan_groups(self, game_ui_root):
        groups = {}
        for current, dirs, _files in os.walk(game_ui_root, followlinks=False):
            dirs[:] = sorted(
                [name for name in dirs if _inside(os.path.join(current, name), game_ui_root)],
                key=str.casefold,
            )
            if os.path.normcase(current) == os.path.normcase(game_ui_root):
                continue
            real = os.path.realpath(current)
            if not _inside(real, game_ui_root):
                continue
            rel = os.path.relpath(real, game_ui_root).replace("\\", "/")
            group_id = _stable_id("grp", real)
            groups[group_id] = {
                "id": group_id, "path": real, "relative_path": rel,
                "name": os.path.basename(real),
            }
        return groups

    def _scan_source_images(self, game_ui_root):
        index = defaultdict(list)
        for current, dirs, files in os.walk(game_ui_root, followlinks=False):
            dirs[:] = sorted(
                [name for name in dirs if _inside(os.path.join(current, name), game_ui_root)],
                key=str.casefold,
            )
            for filename in files:
                if not filename.lower().endswith(".png"):
                    continue
                path = os.path.realpath(os.path.join(current, filename))
                if _inside(path, game_ui_root) and os.path.isfile(path + ".meta"):
                    index[filename.casefold()].append(path)
        return index

    def _scan_prefab(self, path, context, atlas_index, groups, images, image_index):
        with open(path, "rb") as stream:
            data = stream.read()
        refs, _lines = _parse_prefab_bytes(data)
        prefab_id = _stable_id("pfb", path)
        references = []
        source_groups = set()
        missing = 0
        for (guid, file_id), count in sorted(refs.items()):
            resolved = self._resolve_source(atlas_index, guid, file_id)
            reference = {
                "id": _stable_id("ref", "%s|%s|%s" % (path, guid, file_id)),
                "guid": guid, "file_id": file_id, "count": count,
                "status": "missing", "error": "", "sprite_name": "",
                "source_group_id": "", "source_image_id": "",
            }
            if resolved:
                name, group_token = resolved
                image_path, group_path = self._locate_source_image(
                    context["game_ui_root"], group_token, name, image_index
                )
                if image_path:
                    image_id = _stable_id("img", image_path)
                    group_id = _stable_id("grp", group_path)
                    if group_id not in groups:
                        reference["error"] = "源 PNG 所在图集组不存在"
                        missing += 1
                    else:
                        images.setdefault(image_id, {
                            "id": image_id, "path": image_path,
                            "meta_path": image_path + ".meta", "name": os.path.splitext(os.path.basename(image_path))[0],
                            "source_group_id": group_id,
                            "source_group": os.path.relpath(group_path, context["game_ui_root"]).replace("\\", "/"),
                        })
                        reference.update({
                            "status": "ready", "sprite_name": name,
                            "source_group_id": group_id, "source_image_id": image_id,
                        })
                        source_groups.add(group_id)
                else:
                    reference["error"] = "找不到唯一源 PNG 或相邻 meta"
                    missing += 1
            else:
                reference["error"] = "Atlas GUID/fileID 缺失或歧义"
                missing += 1
            references.append(reference)
        return {
            "id": prefab_id, "path": path,
            "relative_path": os.path.relpath(path, context["prefab_root"]).replace("\\", "/"),
            "references": references, "source_group_count": len(source_groups),
            "missing_count": missing, "rewrite": {"status": "pending", "error": ""},
            "manual_group_ids": [],
        }

    @staticmethod
    def _resolve_source(atlas_index, guid, file_id):
        records = atlas_index["by_guid"].get(guid, [])
        if len(records) != 1:
            return None
        names = {name for candidate_id, name in records[0]["pairs"] if candidate_id == file_id}
        if len(names) != 1:
            return None
        name = next(iter(names))
        matching_ids = {candidate_id for candidate_id, candidate_name in records[0]["pairs"] if candidate_name == name}
        if len(matching_ids) != 1:
            return None
        tokens = records[0]["tokens"]
        group = min(tokens, key=lambda token: (token.count("/"), len(token))) if tokens else ""
        return name, group

    @staticmethod
    def _locate_source_image(game_ui_root, group_token, sprite_name, image_index):
        directory = os.path.realpath(
            os.path.join(game_ui_root, group_token.replace("/", os.sep))
        )
        if not _inside(directory, game_ui_root):
            return None, None
        matches = [
            path for path in image_index.get((sprite_name + ".png").casefold(), [])
            if os.path.normcase(os.path.dirname(path)) == os.path.normcase(directory)
        ]
        return (matches[0], directory) if len(matches) == 1 else (None, None)

    def _add_plan(self, draft, prefab_id, source_image_id, target_group_id, origin, refresh=True):
        prefab = self._prefab(draft, prefab_id)
        image = draft["images"].get(source_image_id)
        if not image:
            raise AtlasMigrationError("源图片不存在")
        references = [
            item["id"] for item in prefab["references"]
            if item.get("source_image_id") == source_image_id
        ]
        if not references:
            raise AtlasMigrationError("该预制不引用此源图片")
        target_group = self._group(draft, target_group_id)
        existing = self._plan_for(draft, prefab_id, source_image_id)
        if existing:
            existing_copy = draft["copies"][existing["copy_id"]]
            if existing_copy.get("status") == "success":
                raise AtlasMigrationError("已复制的资源不能修改迁移目标")
            self._unlink_plan(draft, existing["id"])
        copy_key = os.path.normcase(os.path.realpath(image["path"])) + "|" + os.path.normcase(target_group["path"])
        copy_id = _stable_id("cpy", copy_key)
        if copy_id not in draft["copies"]:
            desired = _target_prefix_name(image["name"], target_group["name"])
            desired = self._available_auto_name(draft, target_group, desired, copy_id)
            draft["copies"][copy_id] = {
                "id": copy_id, "source_path": image["path"], "source_meta_path": image["meta_path"],
                "target_group_id": target_group_id, "target_name": desired,
                "auto_base_name": _target_prefix_name(image["name"], target_group["name"]),
                "manual_name": False, "conflict": "", "status": "pending", "error": "", "plan_ids": [],
            }
        plan_id = _stable_id("pln", "%s|%s" % (prefab_id, source_image_id))
        draft["plans"][plan_id] = {
            "id": plan_id, "prefab_id": prefab_id, "source_image_id": source_image_id,
            "target_group_id": target_group_id, "copy_id": copy_id,
            "reference_ids": references, "origin": origin,
            "resolution": {"status": "pending", "error": ""},
            "rewrite": {"status": "pending", "error": ""},
        }
        draft["copies"][copy_id]["plan_ids"].append(plan_id)
        if refresh:
            self._refresh_conflicts(draft)

    def _unlink_plan(self, draft, plan_id):
        plan = draft["plans"].pop(plan_id)
        copy_id = plan.get("copy_id")
        if not copy_id:
            return
        item = draft["copies"][copy_id]
        item["plan_ids"] = [value for value in item["plan_ids"] if value != plan_id]
        if not item["plan_ids"]:
            del draft["copies"][copy_id]

    def _available_auto_name(self, draft, group, desired, own_copy_id):
        candidate = desired
        number = 0
        reserved = {
            item["target_name"].casefold() for copy_id, item in draft["copies"].items()
            if copy_id != own_copy_id and item["target_group_id"] == group["id"]
        }
        while self._name_exists(group["path"], candidate) or candidate.casefold() in reserved:
            number += 1
            candidate = "%s_rename%d" % (desired, number)
        return candidate

    @staticmethod
    def _name_exists(directory, name):
        wanted = {(name + ".png").casefold(), (name + ".png.meta").casefold()}
        try:
            return any(filename.casefold() in wanted for filename in os.listdir(directory))
        except OSError:
            return True

    def _refresh_conflicts(self, draft):
        for item in draft["copies"].values():
            item["conflict"] = ""
        for item in draft["copies"].values():
            if item.get("status") == "success" or item.get("manual_name"):
                continue
            group = self._group(draft, item["target_group_id"])
            base = item.get("auto_base_name") or re.sub(
                r"_rename\d+$", "", item["target_name"], flags=re.IGNORECASE
            )
            item["auto_base_name"] = base
            duplicate = any(
                other["id"] != item["id"]
                and other["target_group_id"] == item["target_group_id"]
                and other["target_name"].casefold() == item["target_name"].casefold()
                for other in draft["copies"].values()
            )
            if self._name_exists(group["path"], item["target_name"]) or duplicate:
                item["target_name"] = self._available_auto_name(
                    draft, group, base, item["id"]
                )
        buckets = defaultdict(list)
        for item in draft["copies"].values():
            buckets[(item["target_group_id"], item["target_name"].casefold())].append(item)
        for bucket in buckets.values():
            if len(bucket) > 1:
                for item in bucket:
                    item["conflict"] = "目标名称已被草稿中的其他资源占用"
        for item in draft["copies"].values():
            if item.get("status") == "success":
                continue
            group = self._group(draft, item["target_group_id"])
            if self._name_exists(group["path"], item["target_name"]):
                item["conflict"] = "目标目录已存在同名 PNG 或 meta"

    def _copy_pair(self, item):
        source = item["source_path"]
        source_meta = item["source_meta_path"]
        if not os.path.isfile(source) or not os.path.isfile(source_meta):
            raise AtlasMigrationError("源 PNG 或 meta 不存在")
        target_dir = item["target_dir"]
        target_png = os.path.join(target_dir, item["target_name"] + ".png")
        target_meta = target_png + ".meta"
        if self._name_exists(target_dir, item["target_name"]):
            raise AtlasMigrationError("目标 PNG 或 meta 已存在")
        staged = []
        claimed = []
        completed = False
        try:
            for source_path, suffix in ((source, ".png.tmp"), (source_meta, ".meta.tmp")):
                fd, temp_path = tempfile.mkstemp(prefix=".atlas_migration_", suffix=suffix, dir=target_dir)
                os.close(fd)
                staged.append(temp_path)
                shutil.copy2(source_path, temp_path)
                with open(temp_path, "rb+") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
                if os.path.getsize(temp_path) != os.path.getsize(source_path):
                    raise OSError("暂存文件校验失败")
            for target_path in (target_png, target_meta):
                descriptor = os.open(target_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(descriptor)
                claimed.append(target_path)
            os.replace(staged[0], target_png)
            staged[0] = ""
            os.replace(staged[1], target_meta)
            staged[1] = ""
            completed = True
        finally:
            if not completed:
                for path in claimed:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            for path in staged:
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    def _find_final_matches(self, atlas_index, group, target_name):
        rel = group["relative_path"].replace("\\", "/").strip("/").casefold()
        exact = []
        for record in atlas_index["records"]:
            by_id = defaultdict(set)
            by_name = defaultdict(set)
            for file_id, name in record["pairs"]:
                by_id[file_id].add(name)
                by_name[name].add(file_id)
            if len(by_name.get(target_name, set())) != 1:
                continue
            file_id = next(iter(by_name[target_name]))
            if len(by_id[file_id]) != 1:
                continue
            candidate = (record["guid"], file_id)
            duplicate_count = 2 if len(atlas_index["by_guid"][record["guid"]]) > 1 else 1
            if rel in record["tokens"]:
                exact.extend([candidate] * duplicate_count)
        return sorted(exact)

    def _revalidate_rewrites(self, draft, log=None):
        completed = draft.get("completed_plans", [])
        for prefab in draft["prefabs"]:
            plans = [
                item for item in draft["plans"].values()
                if item["prefab_id"] == prefab["id"]
            ]
            archived = [item for item in completed if item["prefab_id"] == prefab["id"]]
            successful = [
                item for item in plans
                if item.get("rewrite", {}).get("status") == "success"
            ] + archived
            if successful:
                with open(prefab["path"], "rb") as stream:
                    current, _lines = _parse_prefab_bytes(stream.read())
                old_keys = set()
                expected = Counter()
                for plan in successful:
                    resolution = plan["resolution"]
                    for reference_id in plan["reference_ids"]:
                        reference = next(
                            (item for item in prefab["references"] if item["id"] == reference_id),
                            None,
                        )
                        if reference is None:
                            snapshot = plan.get("source_snapshot") or {}
                            if not snapshot:
                                continue
                            old_keys.add((snapshot["guid"], snapshot["file_id"]))
                            expected[(resolution["guid"], int(resolution["file_id"]))] += snapshot.get("count", 1)
                            continue
                        old_keys.add((reference["guid"], reference["file_id"]))
                        expected[(resolution["guid"], int(resolution["file_id"]))] += reference["count"]
                valid = all(current.get(key, 0) == 0 for key in old_keys) and all(
                    current.get(key, 0) >= count for key, count in expected.items()
                )
                if not valid:
                    for plan in successful:
                        plan["rewrite"] = {"status": "failed", "error": "当前预制的新引用命中次数已变化"}
                    for item in archived:
                        if item in completed:
                            completed.remove(item)
                            draft["plans"][item["id"]] = item
                            copy_id = item.get("copy_id")
                            if copy_id and copy_id in draft["copies"]:
                                draft["copies"][copy_id]["plan_ids"].append(item["id"])
                    _log(log, "预制复核失败: %s (%s)" % (prefab["relative_path"], "当前预制的新引用命中次数已变化"))
            self._refresh_prefab_rewrite(prefab, plans + archived)

    @staticmethod
    def _source_snapshot(draft, prefab, plan):
        reference = next(
            (item for item in prefab["references"] if item["id"] in plan.get("reference_ids", [])),
            None,
        )
        if not reference:
            return {}
        source_group = ""
        if reference.get("source_image_id"):
            source_group = draft["images"].get(reference["source_image_id"], {}).get("source_group", "")
        return {
            "guid": reference["guid"],
            "file_id": reference["file_id"],
            "count": reference["count"],
            "sprite_name": reference.get("sprite_name", ""),
            "source_group": source_group,
        }

    def _archive_completed_plans(self, draft):
        completed = draft.setdefault("completed_plans", [])
        for plan_id, plan in list(draft["plans"].items()):
            if plan.get("rewrite", {}).get("status") != "success":
                continue
            copy_id = plan.get("copy_id")
            if copy_id and copy_id in draft["copies"]:
                item = draft["copies"][copy_id]
                item["plan_ids"] = [value for value in item["plan_ids"] if value != plan_id]
            plan["source_snapshot"] = plan.get("source_snapshot") or {}
            completed.append(plan)
            del draft["plans"][plan_id]
        return completed

    def _refresh_prefab_references(self, draft):
        atlas_index = _scan_atlas(draft["atlas_root"])
        image_index = self._scan_source_images(draft["game_ui_root"])
        groups = draft["groups"]
        images = draft["images"]
        context = {"prefab_root": draft["prefab_root"], "game_ui_root": draft["game_ui_root"]}
        for index, prefab in enumerate(draft["prefabs"]):
            refreshed = self._scan_prefab(
                prefab["path"], context, atlas_index, groups, images, image_index
            )
            refreshed["id"] = prefab["id"]
            draft["prefabs"][index] = refreshed
            plans = [item for item in draft["plans"].values() if item["prefab_id"] == prefab["id"]]
            all_plans = plans + [
                item for item in draft.get("completed_plans", [])
                if item["prefab_id"] == prefab["id"]
            ]
            self._refresh_prefab_rewrite(refreshed, all_plans)

    def _verify_manual_targets(self, draft, log=None, atlas_index=None):
        pending_manual = [
            plan for plan in draft["plans"].values()
            if plan.get("kind") == "manual"
            and plan.get("rewrite", {}).get("status") != "success"
        ]
        if not pending_manual:
            return []
        if atlas_index is None:
            atlas_index = _scan_atlas(draft["atlas_root"])
        removed = []
        for plan in pending_manual:
            plan_id = plan["id"]
            if not self._manual_target_still_valid(atlas_index, plan):
                removed.append(plan_id)
                del draft["plans"][plan_id]
                if log:
                    _log(log, "已移除失效的手动指定计划: %s" % plan_id)
        return removed

    @staticmethod
    def _manual_target_still_valid(atlas_index, plan):
        resolution = plan.get("resolution", {})
        if resolution.get("status") != "success":
            return False
        guid = resolution.get("guid", "")
        try:
            file_id = int(resolution.get("file_id", -1))
        except (TypeError, ValueError):
            return False
        name = plan.get("target_sprite_name", "")
        records = atlas_index["by_guid"].get(guid, [])
        if len(records) != 1:
            return False
        record = records[0]
        same_id = {entry_name for entry_id, entry_name in record["pairs"] if entry_id == file_id}
        same_name = {entry_id for entry_id, entry_name in record["pairs"] if entry_name == name}
        return (
            len(same_id) == 1
            and name in same_id
            and len(same_name) == 1
            and file_id in same_name
        )

    def refresh_atlas_catalog(self, draft_id, log=None):
        with self._lock(draft_id):
            draft = self._load(draft_id)
            atlas_index = _scan_atlas(draft["atlas_root"])
            draft["atlases"] = _build_atlas_catalog(draft["atlas_root"], atlas_index)
            removed = self._verify_manual_targets(draft, log, atlas_index=atlas_index)
            self._refresh_stage(draft)
            self._save(draft)
            return {"draft": self._view(draft), "removed": removed}

    @staticmethod
    def _refresh_prefab_rewrite(prefab, plans):
        if not plans:
            prefab["rewrite"] = {"status": "pending", "error": ""}
            return
        statuses = [item.get("rewrite", {}).get("status", "pending") for item in plans]
        errors = [
            item.get("rewrite", {}).get("error", "") for item in plans
            if item.get("rewrite", {}).get("error")
        ]
        if all(status == "success" for status in statuses):
            status = "success"
        elif any(status == "success" for status in statuses):
            status = "partial"
        elif any(status == "failed" for status in statuses):
            status = "failed"
        else:
            status = "pending"
        prefab["rewrite"] = {"status": status, "error": "; ".join(dict.fromkeys(errors))}

    def _rewrite_one(self, draft, prefab, plans):
        with open(prefab["path"], "rb") as stream:
            original = stream.read()
        current, _lines = _parse_prefab_bytes(original)
        replacements = {}
        removed = Counter()
        added = Counter()
        for plan in plans:
            resolution = plan.get("resolution", {})
            if resolution.get("status") != "success":
                raise AtlasMigrationError("存在未解析的计划")
            old_counts = Counter()
            new_counts = Counter()
            for reference_id in plan["reference_ids"]:
                reference = next(item for item in prefab["references"] if item["id"] == reference_id)
                old = (reference["guid"], reference["file_id"])
                new = (resolution["guid"], int(resolution["file_id"]))
                old_counts[old] += reference["count"]
                new_counts[new] += reference["count"]
            pending = all(current.get(key, 0) == count for key, count in old_counts.items())
            applied = all(current.get(key, 0) == 0 for key in old_counts)
            if not pending and not applied:
                raise AtlasMigrationError("引用命中次数既非待修改状态也非已应用状态")
            if pending:
                removed.update(old_counts)
                added.update(new_counts)
                for old in old_counts:
                    replacements[old] = next(iter(new_counts))
        candidate = _FIELD_LINE_RE.sub(lambda match: self._rewrite_line(match, replacements), original)
        after, _ = _parse_prefab_bytes(candidate)
        for key in set(removed) | set(added):
            expected_final = current.get(key, 0) - removed.get(key, 0) + added.get(key, 0)
            if after.get(key, 0) != expected_final:
                raise AtlasMigrationError("候选内容的新引用数量不正确")
        if candidate != original:
            self._validate_draft(draft)
            self._atomic_bytes(prefab["path"], candidate)

    @staticmethod
    def _rewrite_line(match, replacements):
        body = match.group("body")
        file_match = _FILE_ID_BYTES_RE.search(body)
        guid_match = _GUID_BYTES_RE.search(body)
        if not file_match or not guid_match:
            return match.group(0)
        old = (guid_match.group("value").decode("ascii").lower(), int(file_match.group("value")))
        new = replacements.get(old)
        if not new:
            return match.group(0)
        new_guid, new_file_id = new
        body = _FILE_ID_BYTES_RE.sub(
            lambda token: b"fileID" + token.group("sep") + str(new_file_id).encode("ascii"), body, count=1
        )
        body = _GUID_BYTES_RE.sub(
            lambda token: b"guid" + token.group("sep") + new_guid.encode("ascii"), body, count=1
        )
        return match.group("indent") + b"m_Sprite:" + match.group("space") + b"{" + body + b"}" + match.group("trail")

    def _write_report(self, draft):
        self._validate_draft(draft)
        lines = ["图集引用迁移记录", "草稿: %s" % draft["id"], "阶段: %s" % draft["stage"], ""]
        all_plans = list(draft["plans"].values()) + list(draft.get("completed_plans", []))
        for prefab in draft["prefabs"]:
            plans = [item for item in all_plans if item["prefab_id"] == prefab["id"]]
            if not plans:
                continue
            lines.append("[预制] %s" % prefab["relative_path"])
            lines.append("修改状态: %s %s" % (
                prefab.get("rewrite", {}).get("status", "pending"),
                prefab.get("rewrite", {}).get("error", ""),
            ))
            for plan in plans:
                resolution = plan.get("resolution", {})
                rewrite = plan.get("rewrite", {})
                references = [
                    reference for reference in prefab["references"]
                    if reference["id"] in plan["reference_ids"]
                ]
                snapshot = plan.get("source_snapshot") or {}
                old_refs = ", ".join(
                    "%s/%s x%s" % (reference["guid"], reference["file_id"], reference["count"])
                    for reference in references
                ) if references else (
                    "%s/%s x%s" % (snapshot["guid"], snapshot["file_id"], snapshot.get("count", 1))
                    if snapshot else ""
                )
                if plan.get("kind") == "manual":
                    reference = references[0] if references else {}
                    source_group = (
                        draft["images"].get(reference.get("source_image_id", ""), {}).get("source_group", "")
                        if reference else snapshot.get("source_group", "")
                    )
                    sprite_name = reference.get("sprite_name", "") or snapshot.get("sprite_name", "")
                    atlas = draft["atlases"].get(plan.get("target_atlas_id", ""), {})
                    lines.append("- [手动指定] %s/%s(%s) -> %s/%s; new=%s/%s; resolve=%s; rewrite=%s" % (
                        source_group or "未知源组",
                        sprite_name or "未知源Sprite",
                        old_refs,
                        atlas.get("relative_path", "未知目标Atlas"),
                        plan.get("target_sprite_name", "未知目标Sprite"),
                        resolution.get("guid", "-"), resolution.get("file_id", "-"),
                        resolution.get("status", "pending"), rewrite.get("status", "pending"),
                    ))
                    continue
                image = draft["images"][plan["source_image_id"]]
                group = self._group(draft, plan["target_group_id"])
                copy_item = draft["copies"][plan["copy_id"]]
                lines.append("- %s/%s -> %s/%s; source=%s; copy=%s; final=%s/%s; resolve=%s; rewrite=%s" % (
                    image["source_group"], image["name"], group["relative_path"], copy_item["target_name"],
                    old_refs, copy_item.get("status", "pending"), resolution.get("guid", "-"),
                    resolution.get("file_id", "-"), resolution.get("status", "pending"),
                    rewrite.get("status", "pending"),
                ))
            lines.append("")
        lines.append("[去重资源清单]")
        for item in draft["copies"].values():
            group = self._group(draft, item["target_group_id"])
            lines.append("- %s -> %s/%s.png; status=%s" % (
                item["source_path"], group["relative_path"], item["target_name"], item.get("status", "pending")
            ))
        payload = codecs.BOM_UTF8 + ("\r\n".join(lines) + "\r\n").encode("utf-8")
        self._atomic_bytes(draft["txt_path"], payload)

    @staticmethod
    def _atomic_bytes(path, payload):
        directory = os.path.dirname(path)
        fd, temp_path = tempfile.mkstemp(prefix=".atlas_migration_", dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _validate_draft(self, draft):
        try:
            if not isinstance(draft, dict) or draft.get("version") != 2:
                raise AtlasMigrationError("草稿结构无效")
            for key in ("id", "created_at", "updated_at", "stage"):
                if not isinstance(draft.get(key), str):
                    raise AtlasMigrationError("草稿结构无效")
            if not re.match(r"^[0-9a-f]{32}$", draft["id"]):
                raise AtlasMigrationError("草稿结构无效")
            if draft["stage"] not in {
                "planning", "copy_partial", "copied", "resolution_partial",
                "resolved", "rewrite_partial", "completed",
            }:
                raise AtlasMigrationError("草稿阶段无效")
            for key, expected_type in (
                ("prefabs", list), ("images", dict), ("groups", dict),
                ("atlases", dict), ("plans", dict), ("copies", dict),
                ("completed_plans", list), ("diagnostics", list),
            ):
                if not isinstance(draft.get(key), expected_type):
                    raise AtlasMigrationError("草稿结构无效")
            roots = {}
            for key in ("project_root", "input_root", "prefab_root", "atlas_root", "game_ui_root"):
                value = draft.get(key)
                if not isinstance(value, str) or not value:
                    raise AtlasMigrationError("草稿路径无效")
                roots[key] = os.path.realpath(value)
            client_root = os.path.join(roots["project_root"], "Client")
            expected = {
                "prefab_root": os.path.join(client_root, "Assets", "Resources", "UI", "Prefabs"),
                "atlas_root": os.path.join(client_root, "Assets", "Resources", "UI", "Atlas"),
                "game_ui_root": os.path.join(client_root, "Assets", "GameAssets", "UI"),
            }
            for key, value in expected.items():
                if os.path.normcase(roots[key]) != os.path.normcase(os.path.realpath(value)):
                    raise AtlasMigrationError("草稿工程路径结构已损坏")
            if not _inside(roots["input_root"], roots["prefab_root"]):
                raise AtlasMigrationError("草稿输入目录越界")
            prefab_ids = set()
            reference_ids = {}
            for prefab in draft["prefabs"]:
                if not isinstance(prefab, dict) or not isinstance(prefab.get("references"), list):
                    raise AtlasMigrationError("草稿预制结构无效")
                prefab_id, path = prefab.get("id"), prefab.get("path")
                if not isinstance(prefab_id, str) or prefab_id in prefab_ids:
                    raise AtlasMigrationError("草稿预制结构无效")
                if not isinstance(path, str) or not _inside(path, roots["prefab_root"]):
                    raise AtlasMigrationError("草稿预制路径越界")
                prefab_ids.add(prefab_id)
                manual_ids = prefab.get("manual_group_ids")
                if manual_ids is not None:
                    if not isinstance(manual_ids, list):
                        raise AtlasMigrationError("草稿手动图集组结构无效")
                    prefab["manual_group_ids"] = [gid for gid in manual_ids if isinstance(gid, str)]
                else:
                    prefab["manual_group_ids"] = []
                ids = set()
                for reference in prefab["references"]:
                    if not isinstance(reference, dict) or not isinstance(reference.get("id"), str):
                        raise AtlasMigrationError("草稿引用结构无效")
                    if reference["id"] in ids:
                        raise AtlasMigrationError("草稿引用结构无效")
                    ids.add(reference["id"])
                reference_ids[prefab_id] = ids
            for group_id, group in draft["groups"].items():
                if not isinstance(group, dict) or group.get("id") != group_id:
                    raise AtlasMigrationError("草稿图集组结构无效")
                path = group.get("path")
                rel = group.get("relative_path")
                if not isinstance(path, str) or not isinstance(rel, str) or not _inside(path, roots["game_ui_root"]):
                    raise AtlasMigrationError("草稿图集组路径越界")
                derived = os.path.realpath(os.path.join(roots["game_ui_root"], rel.replace("/", os.sep)))
                if os.path.normcase(os.path.realpath(path)) != os.path.normcase(derived):
                    raise AtlasMigrationError("草稿图集组路径不一致")
            for atlas_id, atlas in draft["atlases"].items():
                if not isinstance(atlas, dict) or atlas.get("id") != atlas_id:
                    raise AtlasMigrationError("草稿图集目录结构无效")
                path = atlas.get("path")
                if not isinstance(path, str) or not _inside(path, roots["atlas_root"]):
                    raise AtlasMigrationError("草稿图集路径越界")
                if not isinstance(atlas.get("guid"), str) or not _VALID_GUID_RE.match(atlas["guid"]):
                    raise AtlasMigrationError("草稿图集 GUID 无效")
                if atlas.get("status") not in ("ready", "excluded"):
                    raise AtlasMigrationError("草稿图集状态无效")
                if not isinstance(atlas.get("sprites"), list):
                    raise AtlasMigrationError("草稿图集资源结构无效")
                sprite_ids = set()
                for sprite in atlas["sprites"]:
                    if (
                        not isinstance(sprite, dict)
                        or not isinstance(sprite.get("id"), str)
                        or sprite["id"] in sprite_ids
                        or not isinstance(sprite.get("name"), str)
                        or not isinstance(sprite.get("file_id"), int)
                    ):
                        raise AtlasMigrationError("草稿图集资源结构无效")
                    sprite_ids.add(sprite["id"])
            for image_id, image in draft["images"].items():
                if not isinstance(image, dict) or image.get("id") != image_id:
                    raise AtlasMigrationError("草稿图片结构无效")
                path, meta = image.get("path"), image.get("meta_path")
                group = draft["groups"].get(image.get("source_group_id"))
                if not isinstance(path, str) or not isinstance(meta, str) or not group:
                    raise AtlasMigrationError("草稿图片结构无效")
                if not _inside(path, roots["game_ui_root"]) or not _inside(meta, roots["game_ui_root"]):
                    raise AtlasMigrationError("草稿图片路径越界")
                if os.path.normcase(os.path.realpath(meta)) != os.path.normcase(os.path.realpath(path + ".meta")):
                    raise AtlasMigrationError("草稿图片 meta 路径无效")
                if os.path.normcase(os.path.dirname(os.path.realpath(path))) != os.path.normcase(os.path.realpath(group["path"])):
                    raise AtlasMigrationError("草稿图片源组不一致")
            image_paths = {
                (os.path.normcase(os.path.realpath(item["path"])),
                 os.path.normcase(os.path.realpath(item["meta_path"])))
                for item in draft["images"].values()
            }
            for copy_id, item in draft["copies"].items():
                if not isinstance(item, dict) or item.get("id") != copy_id:
                    raise AtlasMigrationError("草稿复制结构无效")
                group = draft["groups"].get(item.get("target_group_id"))
                if (
                    not group
                    or not isinstance(item.get("source_path"), str)
                    or not isinstance(item.get("source_meta_path"), str)
                    or not isinstance(item.get("plan_ids"), list)
                ):
                    raise AtlasMigrationError("草稿复制结构无效")
                if not _inside(item["source_path"], roots["game_ui_root"]) or not _inside(item["source_meta_path"], roots["game_ui_root"]):
                    raise AtlasMigrationError("草稿复制源路径越界")
                source_pair = (
                    os.path.normcase(os.path.realpath(item["source_path"])),
                    os.path.normcase(os.path.realpath(item["source_meta_path"])),
                )
                if source_pair not in image_paths:
                    raise AtlasMigrationError("草稿复制源路径不一致")
                _validate_basename(item.get("target_name"))
                item["target_dir"] = os.path.realpath(group["path"])
            linked_plan_ids = defaultdict(set)
            for plan_id, plan in draft["plans"].items():
                if not isinstance(plan, dict) or plan.get("id") != plan_id:
                    raise AtlasMigrationError("草稿计划结构无效")
                prefab_id = plan.get("prefab_id")
                if prefab_id not in prefab_ids or not isinstance(plan.get("reference_ids"), list):
                    raise AtlasMigrationError("草稿计划关联无效")
                if not set(plan["reference_ids"]).issubset(reference_ids[prefab_id]):
                    if (
                        plan.get("rewrite", {}).get("status") != "success"
                        and not plan.get("source_snapshot")
                    ):
                        raise AtlasMigrationError("草稿计划关联无效")
                if plan.get("kind") == "manual":
                    resolution = plan.get("resolution", {})
                    if (
                        plan.get("origin") != "manual"
                        or plan.get("target_atlas_id") not in draft["atlases"]
                        or not isinstance(plan.get("target_sprite_name"), str)
                        or resolution.get("status") != "success"
                        or not isinstance(resolution.get("file_id"), int)
                        or not _VALID_GUID_RE.match(resolution.get("guid", ""))
                    ):
                        raise AtlasMigrationError("草稿手动计划关联无效")
                    continue
                copy_id = plan.get("copy_id")
                if (
                    plan.get("source_image_id") not in draft["images"]
                    or plan.get("target_group_id") not in draft["groups"]
                    or copy_id not in draft["copies"]
                ):
                    raise AtlasMigrationError("草稿计划关联无效")
                if draft["copies"][copy_id]["target_group_id"] != plan["target_group_id"]:
                    raise AtlasMigrationError("草稿计划目标组不一致")
                linked_plan_ids[copy_id].add(plan_id)
            for copy_id, item in draft["copies"].items():
                if set(item["plan_ids"]) != linked_plan_ids[copy_id]:
                    raise AtlasMigrationError("草稿复制计划关联无效")
            txt_path = draft.get("txt_path", "")
            if not isinstance(txt_path, str) or (txt_path and not _inside(txt_path, roots["input_root"])):
                raise AtlasMigrationError("草稿报告路径越界")
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, AtlasMigrationError):
                raise
            raise AtlasMigrationError("草稿结构无效") from exc
        return draft

    def _save(self, draft):
        self._validate_draft(draft)
        draft["updated_at"] = _datetime.datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        self._atomic_bytes(self._draft_path(draft["id"]), payload)

    def _load(self, draft_id):
        if not isinstance(draft_id, str) or not re.match(r"^[0-9a-f]{32}$", draft_id):
            raise AtlasMigrationError("草稿 ID 无效")
        path = self._draft_path(draft_id)
        if not os.path.isfile(path):
            raise AtlasMigrationError("草稿不存在")
        with open(path, "r", encoding="utf-8") as stream:
            draft = json.load(stream)
        if draft.get("id") != draft_id:
            raise AtlasMigrationError("草稿内容无效")
        self._upgrade_draft(draft)
        return self._validate_draft(draft)

    @staticmethod
    def _upgrade_draft(draft):
        if draft.get("version") == 1:
            atlas_root = draft.get("atlas_root", "")
            draft["version"] = 2
            draft["atlases"] = _build_atlas_catalog(atlas_root) if isinstance(atlas_root, str) else {}
        draft.setdefault("completed_plans", [])
        return draft

    def _draft_path(self, draft_id):
        return os.path.join(self.drafts_dir, draft_id + ".json")

    def _lock(self, draft_id):
        with self._locks_guard:
            return self._locks.setdefault(draft_id, threading.RLock())

    @staticmethod
    def _view(draft):
        view = copy.deepcopy(draft)
        for item in view.get("copies", {}).values():
            item.pop("target_dir", None)
        return view

    @staticmethod
    def _require_plannable(draft):
        if draft["stage"] == "completed":
            raise AtlasMigrationError("任务已完成，不能修改计划")

    @staticmethod
    def _prefab(draft, prefab_id):
        for item in draft["prefabs"]:
            if item["id"] == prefab_id:
                return item
        raise AtlasMigrationError("预制 ID 无效")

    @staticmethod
    def _group(draft, group_id):
        item = draft["groups"].get(group_id)
        if not item:
            raise AtlasMigrationError("目标图集 ID 无效")
        return item

    @staticmethod
    def _plan(draft, plan_id):
        item = draft["plans"].get(plan_id)
        if not item:
            raise AtlasMigrationError("计划 ID 无效")
        return item

    @staticmethod
    def _plan_for(draft, prefab_id, source_image_id):
        return next((
            item for item in draft["plans"].values()
            if item["prefab_id"] == prefab_id and item.get("source_image_id") == source_image_id
        ), None)

    @staticmethod
    def _plan_for_reference(draft, prefab_id, reference_id):
        return next((
            item for item in draft["plans"].values()
            if item["prefab_id"] == prefab_id and reference_id in item.get("reference_ids", [])
        ), None)

    @staticmethod
    def _refresh_stage(draft):
        plans = list(draft["plans"].values())
        remaining = [
            item for item in plans
            if item.get("rewrite", {}).get("status") != "success"
        ]
        if not plans:
            draft["stage"] = "planning"
        elif not remaining:
            draft["stage"] = "completed"
        elif any(
            item.get("copy_id")
            and draft["copies"][item["copy_id"]].get("status") != "success"
            for item in remaining
        ):
            draft["stage"] = "copy_partial" if any(
                item.get("copy_id")
                and draft["copies"][item["copy_id"]].get("status") == "failed"
                for item in remaining
            ) else "planning"
        elif all(item.get("resolution", {}).get("status") == "success" for item in remaining):
            draft["stage"] = "resolved"
        elif any(
            item.get("copy_id")
            and draft["copies"][item["copy_id"]].get("status") == "success"
            for item in remaining
        ):
            draft["stage"] = "resolution_partial"
        else:
            draft["stage"] = "planning"
