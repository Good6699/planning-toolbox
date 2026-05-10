(async function() {
    function delay(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

    function isOnList() { return location.hash.indexOf('myHomework') > -1; }
    function isOnExam() { return location.hash.indexOf('examination') > -1; }

    function getExamVm() {
        var el = document.querySelector('.page-content');
        return el && el.__vue__;
    }

    function waitFor(fn, sec) {
        return new Promise(function(res, rej) {
            if (fn()) { res(); return; }
            var w = 0, ci = setInterval(function() {
                w++; if (fn()) { clearInterval(ci); res(); }
                else if (w >= sec) { clearInterval(ci); rej(new Error('timeout')); }
            }, 1000);
        });
    }

    async function goToList() {
        if (isOnList()) return;
        location.hash = '#/main/myHomework';
        try { await waitFor(isOnList, 15); } catch(e) {}
        await delay(1000);
    }

    async function clickConfirm() {
        for (var i = 0; i < 10; i++) {
            await delay(300);
            var btn = document.querySelector('.el-message-box__wrapper .el-button--primary');
            if (!btn) btn = document.querySelector('.el-message-box__btns .el-button--primary');
            if (btn) { btn.click(); return; }
        }
    }

    function getExamName() {
        var vm = getExamVm();
        if (vm && vm.examData && vm.examData.paperName) return vm.examData.paperName;
        if (vm && vm.title) return vm.title;
        return '';
    }

    async function enterAndWait() {
        try { await waitFor(isOnExam, 15); } catch(e) { return false; }
        await delay(3000);
        var vm = getExamVm();
        if (!vm || !vm.questionsList) return false;
        var name = getExamName();
        console.log(' ' + (name ? name.slice(0, 30) + ' ' : '') + '(' + vm.questionsList.length + '题)');
        return true;
    }

    function isAllCorrect() {
        var vm = getExamVm();
        if (!vm || !vm.questionsList) return { all: false, detail: '' };
        var ok = 0, total = vm.questionsList.length, anyUnanswered = false, anyWrong = false;
        vm.questionsList.forEach(function(q) {
            var bg = q.bodyGroups && q.bodyGroups[0];
            if (!bg) return;
            if (!q.answered || bg.answerSelectedIndex === undefined) { anyUnanswered = true; return; }
            if (bg.answerSelectedIndex === bg.selectedIndex) ok++;
            else anyWrong = true;
        });
        var detail = ok + '/' + total;
        if (anyUnanswered) detail += ' (有未答题)';
        else if (anyWrong) detail += ' (有错题)';
        return { all: !anyUnanswered && !anyWrong, correct: ok, total: total, detail: detail };
    }

    function extractAnswers() {
        var answers = {};
        var html = document.body.innerHTML;
        var re = /试题答案:<span[^>]*>(\w+)<\/span>/g;
        var idx = 0;
        var vm = getExamVm();
        var match;
        while ((match = re.exec(html)) !== null) {
            var map = {A:0,B:1,C:2,D:3,E:4,F:5};
            if (vm && vm.questionsList && vm.questionsList[idx]) {
                answers[vm.questionsList[idx].no] = map[match[1]] || 0;
            }
            idx++;
        }
        console.log(' 答案:' + idx + '题');
        return answers;
    }

    async function clickRadios(answerMap) {
        var vm = getExamVm();
        var groups = document.querySelectorAll('.el-radio-group');
        var ok = 0;
        for (var i = 0; i < vm.questionsList.length; i++) {
            var q = vm.questionsList[i];
            var ci = answerMap[q.no];
            if (ci === undefined) continue;
            var g = groups[i];
            if (!g) continue;
            var radios = g.querySelectorAll('.el-radio');
            if (!radios[ci]) continue;
            radios[ci].click();
            await delay(150);
            ok++;
        }
        // 同步 Vue
        vm.questionsList.forEach(function(q) {
            var ci = answerMap[q.no];
            if (ci === undefined) return;
            var bg = q.bodyGroups && q.bodyGroups[0];
            if (!bg) return;
            bg.answerSelectedIndex = ci;
            bg.options.forEach(function(o) { o.checked = (o.optionIndex === ci); });
            q.answered = true;
        });
        console.log(' 选中:' + ok + '/' + vm.questionsList.length);
    }

    function clickSubmitBtn() {
        var all = document.querySelectorAll('button');
        for (var i = 0; i < all.length; i++) {
            if (all[i].innerText.trim() === '提交') { all[i].click(); return true; }
        }
        return false;
    }

    function countBtns(text) {
        var n = 0;
        document.querySelectorAll('.el-button--text').forEach(function(b) {
            if (b.innerText.trim() === text) n++;
        });
        return n;
    }

    function nthBtn(text, n) {
        var found = 0;
        var result = null;
        document.querySelectorAll('.el-button--text').forEach(function(b) {
            if (b.innerText.trim() === text) {
                if (found === n) result = b;
                found++;
            }
        });
        return result;
    }

    console.log('='.repeat(50));
    console.log('🤖 自动答题 v9');
    console.log('='.repeat(50));

    await goToList();

    // ==== Phase 1: 把所有"开始作业"空提交，变成"查看作业" ====
    var total = countBtns('开始作业') + countBtns('继续作业');
    console.log('Phase1: ' + total + '个空提交...');

    for (var i = 0; i < total; i++) {
        await goToList();
        var btn = nthBtn('开始作业', 0) || nthBtn('继续作业', 0);
        if (!btn) { console.log('无按钮'); break; }
        btn.click();
        var ok = await enterAndWait();
        if (!ok) { console.log('失败'); continue; }
        clickSubmitBtn();
        await clickConfirm();
        await delay(1500);
        try { await waitFor(isOnList, 15); } catch(e) {}
        console.log(' 空提交' + (i+1) + '/' + total);
    }

    // ==== Phase 2: 逐个"查看作业" → 提答案 → 重做提交 ====
    await goToList();
    var viewTotal = countBtns('查看作业');
    console.log('\nPhase2: ' + viewTotal + '个重做...');

    for (var j = 0; j < viewTotal; j++) {
        await goToList();
        var vBtn = nthBtn('查看作业', j);
        if (!vBtn) { console.log('无查看按钮'); break; }

        console.log('\n[' + (j+1) + '/' + viewTotal + '] 查看');
        vBtn.click();
        var ok = await enterAndWait();
        if (!ok) continue;

        var chk = isAllCorrect();
        console.log(' 答对:' + chk.detail);
        if (chk.all) {
            console.log(' 🎯 已全对，跳过');
            continue;
        }

        var answers = extractAnswers();
        if (Object.keys(answers).length === 0) continue;

        await goToList();

        var rBtn = nthBtn('重做', j);
        if (!rBtn) { console.log('无重做'); break; }

        rBtn.click();
        await clickConfirm();
        ok = await enterAndWait();
        if (!ok) continue;

        await clickRadios(answers);
        await delay(500);

        clickSubmitBtn();
        await clickConfirm();

        await delay(1500);
        try { await waitFor(isOnList, 15); } catch(e) {}
        console.log(' 完成');
    }

    console.log('\n🏆 全部完成');
})();
