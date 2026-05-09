# -*- coding: utf-8 -*-
"""
职业转换卡系统 - 专业策划案
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

def create_doc():
    wb = Workbook()
    ws = wb.active
    ws.title = '职业转换卡系统策划案'
    
    # 样式定义
    title_font = Font(name='微软雅黑', size=16, bold=True)
    h1_font = Font(name='微软雅黑', size=14, bold=True)
    h2_font = Font(name='微软雅黑', size=12, bold=True)
    h3_font = Font(name='微软雅黑', size=11, bold=True)
    body_font = Font(name='微软雅黑', size=10)
    
    title_fill = PatternFill(start_color='2E4057', end_color='2E4057', fill_type='solid')
    h1_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    h2_fill = PatternFill(start_color='B4C7E7', end_color='B4C7E7', fill_type='solid')
    h3_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
    table_header_fill = PatternFill(start_color='5B9BD5', end_color='5B9BD5', fill_type='solid')
    table_alt_fill = PatternFill(start_color='EEF2F7', end_color='EEF2F7', fill_type='solid')
    
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # 列宽
    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 30
    
    r = 1
    
    def cell(row, col, value, font=None, fill=None, align='left', bold=False, border=None, wrap=True):
        c = ws.cell(row=row, column=col, value=value)
        if font:
            c.font = font
        else:
            c.font = body_font
        if fill:
            c.fill = fill
        if align == 'center':
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
        else:
            c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=wrap)
        if border:
            c.border = border
        return c
    
    def merge_cell(row, col_start, col_end, value, font=None, fill=None, align='left', bold=False, border=None, wrap=True):
        ws.merge_cells(start_row=row, start_column=col_start, end_row=row, end_column=col_end)
        c = cell(row, col_start, value, font, fill, align, bold, border, wrap)
        return c
    
    def title_row(text):
        nonlocal r
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = cell(r, 1, text, title_font, title_fill, 'center', True)
        ws.row_dimensions[r].height = 35
        r += 1
    
    def h1(text):
        nonlocal r
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = cell(r, 1, text, h1_font, h1_fill, 'center', True)
        ws.row_dimensions[r].height = 28
        r += 1
    
    def h2(text):
        nonlocal r
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        c = cell(r, 2, text, h2_font, h2_fill, 'left', True)
        ws.row_dimensions[r].height = 24
        r += 1
    
    def h3(text):
        nonlocal r
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        c = cell(r, 2, text, h3_font, h3_fill, 'left', True)
        ws.row_dimensions[r].height = 22
        r += 1
    
    def blank():
        nonlocal r
        r += 1
    
    def text_row(text, indent=2, font=None, fill=None):
        nonlocal r
        ws.merge_cells(start_row=r, start_column=indent, end_row=r, end_column=8)
        c = cell(r, indent, text, font, fill)
        ws.row_dimensions[r].height = 20
        r += 1
    
    def table_header_row(cols, widths=None):
        nonlocal r
        for i, col_name in enumerate(cols):
            col_num = i + 2
            c = cell(r, col_num, col_name, Font(name='微软雅黑', size=10, bold=True, color='FFFFFF'), table_header_fill, 'center', True, thin_border)
        ws.row_dimensions[r].height = 22
        r += 1
    
    def table_row(cols, fill_color=None):
        nonlocal r
        fill = fill_color if r % 2 == 0 else None
        for i, col_val in enumerate(cols):
            col_num = i + 2
            c = cell(r, col_num, col_val, None, fill, 'left', False, thin_border)
        ws.row_dimensions[r].height = 20
        r += 1
    
    # ==================== 封面 ====================
    title_row('职业转换卡系统 · 系统策划案')
    blank()
    
    # 基础信息
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    cell(r, 2, '功能名称', h3_font, h3_fill, 'center', True)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
    cell(r, 4, '职业转换卡系统', body_font, None, 'left', False)
    r += 1
    
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    cell(r, 2, '文档日期', h3_font, h3_fill, 'center', True)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
    cell(r, 4, datetime.now().strftime('%Y年%m月%d日'), body_font, None, 'left', False)
    r += 1
    
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    cell(r, 2, '操作者', h3_font, h3_fill, 'center', True)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
    cell(r, 4, '赵伟', body_font, None, 'left', False)
    r += 1
    
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    cell(r, 2, '版本', h3_font, h3_fill, 'center', True)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
    cell(r, 4, 'V1.0', body_font, None, 'left', False)
    r += 1
    blank()
    
    # ==================== 一、功能概述 ====================
    h1('一、功能概述')
    
    h2('1.1 功能说明')
    text_row('职业转换卡是一种消耗类道具，使用后可将角色转换为指定的非本职业的职业，转换为无损转换。即玩家更换职业后，原有的大部分数据都会完整继承到新职业上。')
    blank()
    
    h2('1.2 转换卡分类')
    table_header_row(['分类', '说明', '使用限制'], [20, 40, 30])
    table_row(['指定职业无损转换卡', '只能转换为卡片指定的职业', '绑定指定职业，不可更改'])
    table_row(['任选职业无损转换卡', '可自由选择任意非本职业进行转换', '无职业限制'], table_alt_fill)
    blank()
    
    h2('1.3 功能入口')
    text_row('入口位置：角色界面 → 新增页签"职业转换"，放在最后面')
    text_row('使用方式：在背包中点击转换卡，跳转至职业转换界面')
    text_row('显示规则：功能开关开启时显示入口，关闭时隐藏入口')
    blank()
    blank()
    
    # ==================== 二，前置条件 ====================
    h1('二、前置条件（前端校验 + 后端校验）')
    
    h2('2.1 前置条件表格')
    table_header_row(['序号', '条件名称', '前端校验', '后端校验', '不满足提示', '说明'])
    conditions = [
        ['1', '可转换的职业', '前端展示时过滤掉本职业', '再次校验目标职业ID有效性', '该职业暂未开放', '需配置转换卡可转换的职业列表'],
        ['2', '可使用等级', '前端获取角色等级展示', '校验角色等级是否满足', '等级不足，需达到XX级', '需配置最低使用等级'],
        ['3', '开服天数限制', '前端获取开服天数', '校验是否满足开服天数', '开服第XX天后可使用', '需配置最低开服天数'],
        ['4', '功能开关', '前端隐藏入口', '校验功能开关状态', '该功能暂未开放', '运营后台可配置'],
        ['5', '非转职冷却时间', '前端显示冷却倒计时', '校验冷却是否结束', '转职冷却中，请XX:XX后再试', '需配置冷却时间'],
        ['6', '非战斗状态', '前端无法打开界面', '校验战斗状态', '请在非战斗状态下使用', '战斗状态不可使用'],
        ['7', '非本职业', '前端过滤本职业', '校验目标职业与当前职业不同', '不能转职为相同职业', '不可转职为本职业'],
        ['8', '在主城', '前端校验场景ID', '校验当前场景是否为主城', '请在主城使用', '需配置主城场景ID'],
        ['9', '消耗道具足够', '前端显示道具数量', '校验背包道具体数', '道具不足', '需配置消耗道具ID和数量'],
    ]
    for i, row in enumerate(conditions):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('2.2 数值配置项')
    table_header_row(['配置项', '字段名', '类型', '默认值', '说明'])
    configs = [
        ['最低使用等级', 'min_level', 'int', '1', '角色需达到的最低等级'],
        ['开服天数限制', 'min_server_day', 'int', '0', '开服后多少天才可使用，0为不限制'],
        ['转职冷却时间', 'cooldown_seconds', 'int', '86400', '两次转职之间的最短间隔（秒），默认24小时'],
        ['功能开关', 'switch_id', 'int', '0', '功能开关ID，0为不限制'],
        ['消耗道具ID', 'item_id', 'int', '0', '转职消耗的道具ID'],
        ['消耗道具数量', 'item_count', 'int', '1', '转职消耗的道具数量'],
        ['可转换职业列表', 'target_jobs', 'string', '', '职业ID列表，逗号分隔，空为所有职业'],
    ]
    for i, row in enumerate(configs):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 三、界面设计 ====================
    h1('三、界面设计')
    
    h2('3.1 职业转换界面布局')
    text_row('界面结构：', 2, h3_font)
    table_header_row(['区域', '内容', '交互说明'])
    table_row(['顶部区域', '页面标题"职业转换"', '固定显示'])
    table_row(['职业列表', '所有可转换职业（卡片形式）', '点击选中，高亮显示'], table_alt_fill)
    table_row(['职业详情', '选中职业的技能展示、模型展示', '随选中职业切换'])
    table_row(['转职规则', '数据继承规则说明', '可折叠展开'], table_alt_fill)
    table_row(['消耗显示', '所需道具及数量', '道具不足时显示红字提示'])
    table_row(['底部区域', '转职按钮', '满足条件可用，不满足置灰'], table_alt_fill)
    blank()
    
    h2('3.2 职业列表展示')
    text_row('展示规则：', 2, h3_font)
    table_header_row(['项目', '规则', 'UI表现'])
    rules = [
        ['本职业', '置底灰化，不可点击', '灰色显示，不可选中'],
        ['已选职业', '高亮边框', '蓝色边框标识'],
        ['不可用职业', '显示锁定图标', '根据具体条件显示不同提示'],
        ['职业技能', '只展示主动技能', '隐藏被动技能'],
        ['职业模型', '用于展示技能效果', '站立待机动画'],
    ]
    for i, row in enumerate(rules):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('3.3 转职确认弹窗')
    text_row('二次确认弹窗：', 2, h3_font)
    table_header_row(['弹窗元素', '内容', '说明'])
    popup = [
        ['标题', '确认转职', ''],
        ['内容', '确认将角色转换为【目标职业】？', '显示目标职业名称'],
        ['消耗展示', '消耗：转换卡 x1', '显示具体消耗'],
        ['确认按钮', '确认', '点击后进入转职流程'],
        ['取消按钮', '取消', '关闭弹窗'],
    ]
    for i, row in enumerate(popup):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('3.4 转职进度界面')
    text_row('进度界面：', 2, h3_font)
    text_row('- 全屏遮罩，背景半透明黑色')
    text_row('- 中央显示转职进度动画/进度条')
    text_row('- 提示文字"转职中，请稍候..."')
    text_row('- 期间禁止一切操作')
    text_row('- 不可点击空白区域关闭')
    blank()
    
    h2('3.5 转职成功弹窗')
    text_row('成功弹窗：', 2, h3_font)
    table_header_row(['元素', '内容'])
    success = [
        ['标题', '转职成功'],
        ['内容', '恭喜！您已成功转换为【目标职业】，需要重启游戏后生效。'],
        ['按钮', '确定（点击后重启游戏）'],
    ]
    for i, row in enumerate(success):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 四、使用流程 ====================
    h1('四、使用流程')
    
    h2('4.1 正常转职流程')
    table_header_row(['步骤', '玩家操作', '前端行为', '后端行为'])
    steps = [
        ['1', '背包点击转换卡', '打开职业转换界面', '推送职业列表、技能列表、消耗信息'],
        ['2', '选择目标职业', '高亮选中，展示职业详情', '记录选中职业ID'],
        ['3', '点击转职按钮', '前端校验前置条件，不满足飘字', '再次校验前置条件'],
        ['4', '弹出二次确认', '显示消耗和目标职业', ''],
        ['5', '点击确认', '按钮进入loading态', '消耗道具，开始转职流程'],
        ['6', '展示转职进度', '全屏遮罩，禁止操作', '执行数据转换'],
        ['7', '转职完成', '弹出成功弹窗', '推送转职结果'],
        ['8', '点击确定', '关闭弹窗，重启游戏', '踢出玩家重新登录'],
    ]
    for i, row in enumerate(steps):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('4.2 中断处理流程')
    table_header_row(['场景', '处理方式', '玩家表现'])
    interrupts = [
        ['转职中途断线', '服务端继续执行转职', '重连后弹窗提示转职进行中'],
        ['转职期间关闭游戏', '服务端继续执行转职', '下次登录如果完成则正常进入'],
        ['转职期间被踢下线', '踢出后自动重连继续', '重连后检查状态继续转职'],
        ['转职完成后断线', '无影响', '下次登录正常进入'],
    ]
    for i, row in enumerate(interrupts):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 五、数据转换细则 ====================
    h1('五、数据转换细则（无损继承规则）')
    
    h2('5.1 角色基础属性')
    table_header_row(['数据项', '转换规则', '前端处理', '后端处理'])
    char_data = [
        ['等级', '数值不变', '刷新等级显示', '继承等级数值'],
        ['转职', '继承转职阶段', '刷新转职图标', '继承转职阶段和进度'],
        ['转生', '数值不变', '刷新转生显示', '继承转生数值'],
        ['性别', '不变', '刷新角色外观', '继承性别'],
        ['VIP', '等级和特权不变', '刷新VIP标识', '继承VIP信息'],
        ['货币', '所有货币数量不变', '刷新货币显示', '继承所有货币'],
        ['经验进度', '百分比不变', '刷新经验条', '继承经验百分比'],
        ['结婚伴侣', '关系保持', '不刷新伴侣信息', '继承伴侣关系'],
        ['公会', '公会信息保持', '不刷新公会信息', '继承公会信息'],
    ]
    for i, row in enumerate(char_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.2 技能系统')
    table_header_row(['数据项', '转换规则', '前端处理', '后端处理'])
    skill_data = [
        ['主动技能', '转换为本职业对应技能', '重新加载技能栏', '删除原职业技能，获得新职业技能'],
        ['技能等级', '继承升级、突破、觉醒等级', '刷新技能图标显示', '继承技能升级/突破/觉醒等级'],
        ['技能配置', '自动适配新职业对应槽位', '提示"技能配置已自动调整"', '保存原配置，映射到新职业槽位'],
        ['技能书', '转换为新职业对应技能书', '刷新背包', '删除原职业技能书，给予新职业技能书'],
        ['突破道具', '转换为新职业对应道具', '刷新背包', '删除原职业道具，给予新职业道具'],
        ['觉醒道具', '转换为新职业对应道具', '刷新背包', '删除原职业道具，给予新职业道具'],
        ['被动技能', '保持不变', '无需处理', '被动技能不区分职业'],
    ]
    for i, row in enumerate(skill_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.3 时装系统')
    table_header_row(['数据项', '转换规则', '前端处理', '后端处理'])
    fashion_data = [
        ['已激活时装', '自动激活新职业对应时装', '刷新时装显示', '激活新职业时装，继承星级'],
        ['时装道具', '转换为新职业对应道具', '刷新背包', '删除原职业时装道具，给予新职业道具'],
        ['时装染色', '继承染色数据', '刷新染色显示', '继承染色配置'],
        ['化妆修改', '继承化妆数据', '刷新外观', '继承化妆修改'],
    ]
    for i, row in enumerate(fashion_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.4 装备系统')
    table_header_row(['数据项', '转换规则', '前端处理', '后端处理'])
    equip_data = [
        ['穿戴装备', '转换为新职业对应装备', '刷新装备显示', '卸下装备，转化给对应装备'],
        ['装备绑定状态', '保持不变', '-', '绑定仍为绑定，可交易仍为可交易'],
        ['装备品质', '保持不变', '-', '白装仍为白装，紫装仍为紫装'],
        ['装备强化', '强化等级继承', '刷新强化显示', '继承强化等级'],
        ['装备镶嵌', '宝石继承', '刷新镶嵌显示', '继承宝石和孔位'],
        ['装备追加', '追加等级继承', '刷新追加显示', '继承追加等级'],
        ['装备卡片', '卡片继承', '刷新卡片显示', '继承卡片'],
        ['装备祝福', '祝福值继承', '刷新祝福显示', '继承祝福值'],
        ['套装石', '转换为本职业对应套装石', '刷新背包', '删除原职业套装石，给予新职业套装石'],
        ['套装激活', '继承激活状态', '刷新套装图标', '重新计算套装效果'],
        ['符文', '转换为本职业对应符文', '刷新背包', '删除原职业符文，给予新职业符文'],
        ['神饰', '继承神饰数据', '刷新神饰显示', '继承神饰'],
        ['魔戒', '不区分职业，不处理', '-', '魔戒全职业通用'],
    ]
    for i, row in enumerate(equip_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.5 其他系统继承')
    table_header_row(['系统', '数据项', '转换规则'])
    other_data = [
        ['称号', '称号列表', '无损继承'],
        ['装扮', '星级', '星级无损继承'],
        ['头衔', '头衔等级', '等级无损继承'],
        ['转生之证', '转生点、技能等级', '无损继承'],
        ['神馈', '神馈数据', '保持不变'],
        ['吞噬', '等级、特权', '无损继承'],
        ['伙伴', '坐骑、翅膀、守护', '无损继承'],
        ['助战', '神像、契约、泰坦、奖杯、圣物', '无损继承'],
        ['神兵', '已激活神兵、升星、器灵', '激活对应神兵，继承升星，继承器灵'],
        ['英雄', '阵容、等级，洗髓、星级、装备等', '无损继承'],
        ['装备收藏', '收藏装备、再生属性', '转化为对应职业，再生属性继承'],
        ['神佑', '英雄圣装、神盾、神甲、神纹', '无损继承'],
        ['伴侣', '伴侣数据', '无损继承'],
        ['公会', '公会数据', '保持不变'],
        ['成就', '职业相关成就', '转化为对应职业成就'],
    ]
    for i, row in enumerate(other_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.6 背包/仓库/邮件处理')
    table_header_row(['道具类型', '转换规则', '处理方式'])
    item_data = [
        ['装备类', '本职业装备', '转换为新职业对应装备'],
        ['道具类', '职业技能书', '转换为新职业技能书'],
        ['道具类', '技能突破道具', '转换为新职业突破道具'],
        ['道具类', '技能觉醒道具', '转换为新职业觉醒道具'],
        ['道具类', '套装石碎片/宝箱', '转换为新职业对应套装石'],
        ['道具类', '神兵/神兵碎片', '转换为新职业对应神兵'],
        ['道具类', '装备宝箱', '转换为新职业对应宝箱'],
        ['其他类', '非职业相关道具', '无损继承，数量绑定状态不变'],
        ['活动临时仓库', '运营活动、寻宝等道具', '按背包规则处理'],
    ]
    for i, row in enumerate(item_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.7 交易行/商店处理')
    table_header_row(['场景', '处理规则', '说明'])
    trade_data = [
        ['上架商品', '保持上架状态和时间', '商品自动转化为新职业对应道具'],
        ['已关注道具', '自动刷新为新职业相关', '不需要玩家重新关注'],
        ['商店道具', '刷新为新职业对应道具', '商店推荐刷新'],
        ['购物单道具', '刷新为新职业对应道具', '购物单刷新'],
    ]
    for i, row in enumerate(trade_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('5.8 外观/奖励匹配')
    table_header_row(['场景', '处理规则'])
    appearance_data = [
        ['主城雕像', '显示新职业形象'],
        ['排行榜', '显示新职业名称和形象'],
        ['天神骑士团', '显示新职业形象'],
        ['位面霸主', '显示新职业形象'],
        ['竞技场结算', '显示新职业形象'],
        ['王者1v1', '显示新职业形象'],
        ['结缘', '显示新职业形象'],
        ['福利/直购/运营活动', '匹配新职业奖励'],
        ['BP/寻宝/首充', '匹配新职业奖励'],
    ]
    for i, row in enumerate(appearance_data):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 六、前端逻辑 ====================
    h1('六、前端逻辑')
    
    h2('6.1 入口显示逻辑')
    text_row('伪代码：', 2, h3_font)
    text_row('IF 功能开关开启 AND 背包有转换卡 THEN 显示入口图标')
    text_row('IF 角色在主城 THEN 入口可点击 ELSE 入口置灰')
    blank()
    
    h2('6.2 界面打开逻辑')
    table_header_row(['步骤', '前端行为', '触发条件'])
    open_logic = [
        ['1', '请求职业列表数据', '点击入口'],
        ['2', '展示职业选择界面', '收到数据后'],
        ['3', '默认选中第一个可用职业', '界面展示完成后'],
        ['4', '展示选中职业详情', '选中职业变化时'],
    ]
    for i, row in enumerate(open_logic):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('6.3 前置条件校验')
    text_row('前端校验项目（仅供参考，实际以后端为准）：', 2, h3_font)
    table_header_row(['条件', '校验方式', '不满足表现'])
    client_check = [
        ['可转换职业', '过滤职业列表', '本职业灰化不可选'],
        ['等级限制', '获取角色等级', '转职按钮置灰+提示'],
        ['道具数量', '获取背包道具数', '消耗显示红字'],
        ['战斗状态', '获取场景状态', '飘字"请在非战斗状态下使用"'],
        ['当前场景', '获取场景ID', '飘字"请在主城使用"'],
    ]
    for i, row in enumerate(client_check):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('6.4 转职按钮状态')
    table_header_row(['状态', '按钮表现', '触发条件'])
    btn_state = [
        ['可点击', '蓝色按钮，可点击', '所有前置条件满足'],
        ['置灰', '灰色按钮，不可点击', '任一前置条件不满足'],
        ['Loading', '显示loading动画', '转职请求发送后'],
    ]
    for i, row in enumerate(btn_state):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 七、后端逻辑 ====================
    h1('七、后端逻辑')
    
    h2('7.1 转职请求协议')
    table_header_row(['字段', '类型', '说明'])
    req_proto = [
        ['type', 'int', '协议号：0xXXXX'],
        ['target_job_id', 'int', '目标职业ID'],
        ['item_uid', 'string', '转换卡道具UID'],
    ]
    for i, row in enumerate(req_proto):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('7.2 转职结果协议')
    table_header_row(['字段', '类型', '说明'])
    resp_proto = [
        ['type', 'int', '协议号：0xXXXX'],
        ['result', 'int', '0成功，1失败'],
        ['error_code', 'int', '错误码'],
        ['new_job_id', 'int', '新职业ID（成功时）'],
        ['error_msg', 'string', '错误信息（失败时）'],
    ]
    for i, row in enumerate(resp_proto):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('7.3 后端处理流程')
    table_header_row(['步骤', '处理内容', '异常处理'])
    backend_flow = [
        ['1', '校验前置条件', '条件不满足返回错误码'],
        ['2', '消耗道具', '消耗失败返回错误码'],
        ['3', '锁定角色', '防止并发操作'],
        ['4', '执行数据转换', '异常回滚道具'],
        ['5', '解锁角色', '确保角色可正常操作'],
        ['6', '推送转职结果', '通知客户端'],
        ['7', '踢出玩家', '强制重新登录'],
    ]
    for i, row in enumerate(backend_flow):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('7.4 错误码定义')
    table_header_row(['错误码', '含义', '前端提示'])
    error_codes = [
        ['1', '功能未开启', '该功能暂未开放'],
        ['2', '等级不足', '等级不足，需达到XX级'],
        ['3', '开服天数不足', '开服第XX天后可使用'],
        ['4', '冷却中', '转职冷却中，请XX:XX后再试'],
        ['5', '在战斗中', '请在非战斗状态下使用'],
        ['6', '不在主城', '请在主城使用'],
        ['7', '道具不足', '道具不足'],
        ['8', '目标职业无效', '该职业暂未开放'],
        ['9', '已是本职业', '不能转职为相同职业'],
        ['10', '转职失败', '转职失败，道具已返还'],
    ]
    for i, row in enumerate(error_codes):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 八、异常处理 ====================
    h1('八、异常处理')
    
    h2('8.1 网络异常')
    table_header_row(['场景', '处理方式', '用户体验'])
    net_error = [
        ['请求超时', '重试3次，间隔2秒', '提示"网络异常，请重试"'],
        ['断线重连', '自动重连', '显示重连中'],
        ['弱网', '增加loading状态', '提示"网络较差"'],
    ]
    for i, row in enumerate(net_error):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('8.2 数据转换异常')
    table_header_row(['异常类型', '处理方式', '补偿措施'])
    data_error = [
        ['职业对应关系未配置', '跳过该类道具', '记录日志，GM手动补偿'],
        ['目标道具不存在', '保留原道具', '记录日志，邮件补发'],
        ['数量溢出', '超出部分转入邮件', '附带说明文字'],
        ['背包空间不足', '优先放入背包', '剩余转入邮件'],
    ]
    for i, row in enumerate(data_error):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('8.3 操作异常')
    table_header_row(['场景', '处理方式'])
    op_error = [
        ['重复点击转职', '按钮进入loading，屏蔽点击', ''],
        ['转职期间切换账号', '强制中断，道具回滚', ''],
        ['转职期间游戏崩溃', '重启后检查状态继续', ''],
    ]
    for i, row in enumerate(op_error):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 九、边界条件 ====================
    h1('九、边界条件')
    
    table_header_row(['场景', '处理方式', '提示信息'])
    boundary = [
        ['同一账号多设备同时操作', '后操作设备提示"当前账号正在转职中"', '"当前账号正在转职中，请稍后"'],
        ['转职冷却时间内再次尝试', '拒绝转职，显示剩余冷却时间', '"转职冷却中，请XX:XX后再试"'],
        ['转职目标与当前职业相同', '按钮置灰，不可点击', '"不能转职为相同职业"'],
        ['背包/仓库/邮件道具数量为0', '跳过转换，不报错', '-'],
        ['目标职业不存在', '转换卡不可使用', '"该职业暂未开放"'],
        ['开服天数不足', '转职按钮置灰', '"开服第XX天后可使用"'],
    ]
    for i, row in enumerate(boundary):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 十、性能要求 ====================
    h1('十、性能要求')
    
    table_header_row(['指标', '要求', '说明'])
    perf = [
        ['界面加载时间', '小于等于2秒', '职业转换界面从打开到可交互'],
        ['转职流程耗时', '小于等于30秒', '从确认到完成的平均耗时'],
        ['内存占用', '峰值小于等于100MB', '功能运行时内存峰值'],
        ['内存泄漏', '1小时增长小于等于5MB', '连续运行内存增长'],
    ]
    for i, row in enumerate(perf):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 十一、安全防刷 ====================
    h1('十一、安全防刷')
    
    table_header_row(['防护类型', '规则', '说明'])
    security = [
        ['点击频率限制', '转职按钮1秒内最多响应1次', '防止快速重复点击'],
        ['请求频率限制', '同一API 1秒内最多请求5次', '防止接口滥用'],
        ['操作频率限制', '转职操作5分钟内只能进行1次', '防止频繁转职'],
        ['账号每日限制', '同一账号1天内最多转换3次', '防止工作室刷职业'],
        ['服务端校验', '所有转职相关操作二次校验', '防止客户端伪造数据'],
        ['职业切换记录', '记录每次转职操作日志', '便于异常追溯'],
    ]
    for i, row in enumerate(security):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 十二、兼容性 ====================
    h1('十二、兼容性')
    
    table_header_row(['项目', '要求', '说明'])
    compat = [
        ['Android最低版本', 'Android 5.0 (API 21)', '低端机2GB内存，功能降级'],
        ['iOS最低版本', 'iOS 12.0', 'iPhone 6s及以上'],
        ['分辨率适配', '16:9、18:9、19.5:9、20:9', '支持平板横竖屏'],
        ['网络环境', 'WiFi、4G、5G、弱网', '弱网提示"网络较差，转职可能失败"'],
        ['数据版本', '新旧版本数据兼容', '转职后数据格式正确'],
    ]
    for i, row in enumerate(compat):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # ==================== 十三、红点/公告/邮件 ====================
    h1('十三、红点/公告/邮件')
    
    h2('13.1 红点提示')
    table_header_row(['类型', '位置', '出现条件', '消失条件'])
    reddot = [
        ['职业转换红点', '角色界面页签', '拥有可使用的转换卡且满足条件', '没有可用转换卡或功能关闭'],
    ]
    for i, row in enumerate(reddot):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    
    h2('13.2 系统公告')
    text_row('转职成功后发送全服公告：')
    text_row('"[玩家名字]成功转职为[新职业名称]，实力大增！"')
    blank()
    
    h2('13.3 邮件通知')
    table_header_row(['场景', '标题', '内容'])
    mail = [
        ['转职过程数据异常', '职业转换补偿', '您在职业转换过程中遇到异常，以下是为您补发的道具。'],
    ]
    for i, row in enumerate(mail):
        fill = table_alt_fill if i % 2 == 1 else None
        table_row(row, fill)
    blank()
    blank()
    
    # 保存
    output_path = r'E:\桌面\其它\职业转换卡系统策划案_专业版.xlsx'
    wb.save(output_path)
    print('策划案已生成: {}'.format(output_path))
    print('总行数: {}'.format(r))

if __name__ == '__main__':
    create_doc()
