(function() {
    function delay(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

    function isOnCourseList() {
        return document.querySelectorAll('.course-card').length > 0;
    }

    function isOnLessonPage() {
        return document.querySelectorAll('a.lesson').length > 0;
    }

    function clickCourse(name) {
        var cards = document.querySelectorAll('.course-card');
        for (var c of cards) {
            var n = c.querySelector('.course-name');
            if (n && n.innerText.includes(name)) { c.click(); return true; }
        }
        return false;
    }

    function waitForCondition(fn, sec) {
        return new Promise(function(res, rej) {
            if (fn()) { res(); return; }
            var w = 0, ci = setInterval(function() {
                w++;
                if (fn()) { clearInterval(ci); res(); }
                else if (w >= sec) { clearInterval(ci); rej('超时'); }
            }, 1000);
        });
    }

    function getVm() {
        var el = document.querySelector('a.lesson.active, a.lesson');
        while (el) { if (el.__vue__) return el.__vue__; el = el.parentElement; }
        return null;
    }

    // 查每个课时 learningRecordDetail 是否有 duration 明细
    function inspectLessonRecords(vm) {
        var lessons = vm.lessons || [];
        var details = [];
        lessons.forEach(function(l, i) {
            details.push({
                index: i,
                lessonId: l.lessonId,
                name: (l.lessonName || '').slice(0, 25),
                isComplete: l.isComplete,
                learningLength: l.learningLength || 0,
                learningRecordDetailId: l.learningRecordDetailId,
                // 这些字段可能存了实际已报时长
                studyTime: l.studyTime,
                lastTime: l.lastTime
            });
        });
        return details;
    }

    // 尝试不同的 API 调用方式
    async function callApi(lessonId, studyRecordId, token, extra) {
        var body = {
            isReplay: extra.isReplay || false,
            lessonId: lessonId,
            studyRecordId: studyRecordId,
            isOver: extra.isOver !== undefined ? extra.isOver : true
        };
        // 有的版本接受 duration 字段
        if (extra.durationMs) body.duration = extra.durationMs;

        var resp = await fetch('/api/adult/student/study/duration', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(body)
        });
        var text = await resp.text();
        return { status: resp.status, body: text };
    }

    async function run() {
        console.log('');
        console.log('========================================');
        console.log('   深度诊断：形势与政策 duration 缺口');
        console.log('========================================');
        console.log('');

        // 1. 进入
        if (!isOnCourseList()) { window.location.hash = '#/main/home'; await delay(2000); }
        if (!isOnCourseList()) { console.log('❌ 不在列表'); return; }
        clickCourse('形势与政策');
        try { await waitForCondition(isOnLessonPage, 10); } catch(e) { console.log('❌ 超时'); return; }
        await delay(3000);

        var vm = getVm();
        if (!vm) { console.log('❌ 无 Vue'); return; }
        var sc = vm.studyCourse || {};
        console.log('[1] studyCourse:');
        for (var k in sc) {
            if (typeof sc[k] !== 'object') console.log('    ' + k + ' = ' + sc[k]);
        }

        var token = sessionStorage.getItem('token');
        console.log('    token=' + (token ? token.slice(0, 20) + '...' : '无'));

        // 2. 查看各课时状态
        console.log('');
        var lessons = vm.lessons || [];
        console.log('[2] 逐课时 look at actual recorded time:');
        var totalRecorded = 0;
        lessons.forEach(function(l) {
            totalRecorded += l.learningLength || 0;
            console.log('  #' + l.lessonId + ' ' + (l.lessonName||'').slice(0,22) +
                '  isComplete=' + l.isComplete +
                '  learningLength=' + (l.learningLength||0) +
                '  detailId=' + (l.learningRecordDetailId||'-'));
        });
        console.log('  理论 sumDuration=' + totalRecorded);

        // 3. 重新用 isReplay=true 试
        console.log('');
        console.log('[3] 用不同参数重试 API...');
        var studyRecordId = sc.studyRecordId;
        var testLessons = [53444, 53453]; // 两个1分钟课时

        for (var ti = 0; ti < testLessons.length; ti++) {
            var lid = testLessons[ti];
            console.log('');
            console.log('  lessonId=' + lid);

            // 试: isReplay=true, isOver=true
            var r1 = await callApi(lid, studyRecordId, token, { isReplay: true, isOver: true });
            console.log('    isReplay=true, isOver=true → ' + r1.status + ' ' + r1.body.slice(0, 100));

            // 试: isOver=false (模拟播放中)
            var r2 = await callApi(lid, studyRecordId, token, { isReplay: false, isOver: false });
            console.log('    isReplay=false, isOver=false → ' + r2.status + ' ' + r2.body.slice(0, 100));

            // 过3秒后 isOver=true
            await delay(3000);
            var r3 = await callApi(lid, studyRecordId, token, { isReplay: false, isOver: true });
            console.log('    (3s后) isOver=true → ' + r3.status + ' ' + r3.body.slice(0, 100));
        }

        // 4. 回到列表看结果
        console.log('');
        console.log('[4] 检查结果...');
        window.location.hash = '#/main/home';
        await delay(3000);
        var cards = document.querySelectorAll('.course-card');
        for (var c of cards) {
            var n = c.querySelector('.course-name');
            if (n && n.innerText.includes('形势与政策')) {
                console.log('  卡片: ' + c.innerText.replace(/\s+/g, ' '));
                break;
            }
        }

        console.log('');
        console.log('========================================');
        console.log('   诊断完成，请查看上面的 isOver=false 返回是否有新记录');
        console.log('========================================');
    }
    run();

})();
