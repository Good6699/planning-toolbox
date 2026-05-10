(function() {
    function delay(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

    function isOnCourseList() {
        return document.querySelectorAll('.course-card').length > 0;
    }

    function isOnLessonPage() {
        return document.querySelectorAll('a.lesson').length > 0;
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

    function getCourseList() {
        var cards = document.querySelectorAll('.course-card');
        return Array.from(cards).map(function(card) {
            var nameEl = card.querySelector('.course-name');
            return nameEl ? nameEl.innerText.trim() : null;
        }).filter(function(n) { return n !== null; });
    }

    function clickCourse(name) {
        var cards = document.querySelectorAll('.course-card');
        for (var c of cards) {
            var n = c.querySelector('.course-name');
            if (n && n.innerText.includes(name)) { c.click(); return true; }
        }
        return false;
    }

    async function goToCourseList() {
        if (isOnCourseList()) return;
        window.location.hash = '#/main/home';
        try { await waitForCondition(isOnCourseList, 10); } catch(e) {}
        await delay(2000);
    }

    async function enterCourse(name) {
        if (!clickCourse(name)) throw '未找到课程: ' + name;
        try { await waitForCondition(isOnLessonPage, 10); } catch(e) { throw '课时加载超时'; }
        await delay(3000);
    }

    function getVm() {
        var el = document.querySelector('a.lesson.active, a.lesson');
        while (el) { if (el.__vue__) return el.__vue__; el = el.parentElement; }
        return null;
    }

    function getLessons() {
        var items = document.querySelectorAll('a.lesson');
        var vm = getVm();
        var vueLessons = (vm && vm.lessons) || [];
        return Array.from(items).map(function(el, i) {
            var vl = vueLessons[i] || {};
            return {
                el: el,
                name: el.innerText.trim(),
                index: i,
                isComplete: !!vl.isComplete,
                isActive: el.classList.contains('active'),
                lessonId: vl.lessonId
            };
        });
    }

    function getUncompleted() {
        return getLessons().filter(function(l) { return !l.isComplete; });
    }

    function countCompleted() {
        return getLessons().filter(function(l) { return l.isComplete; }).length;
    }

    async function waitLessonComplete(lessonEl) {
        while (true) {
            var vm = getVm();
            if (vm && vm.selectedLesson && vm.selectedLesson.isComplete) return true;
            if (lessonEl.querySelector('.text-success')) return true;
            await delay(2000);
        }
    }

    async function learnCurrentCourse() {
        var total = getLessons().length;
        if (total === 0) { console.log('  当前课程无课时'); return; }

        var lastTodoCount = -1;
        var stuckCount = 0;

        while (true) {
            var todo = getUncompleted();
            var done = countCompleted();
            if (todo.length === 0 || done >= total) {
                console.log('\n🎉 当前课程全部完成！(' + done + '/' + total + ')');
                return;
            }

            // 防死循环：连续3轮未学数不变就退出
            if (todo.length === lastTodoCount) {
                stuckCount++;
                if (stuckCount >= 3) {
                    console.log('  ⚠️ 连续' + stuckCount + '轮无进展，退出课程');
                    return;
                }
            } else {
                stuckCount = 0;
            }
            lastTodoCount = todo.length;

            console.log('\n📚 已学 ' + done + '/' + total + ', 剩余 ' + todo.length + ' 个');

            var cur = todo[0];
            console.log('  ▶ ' + cur.name.slice(0, 15));
            cur.el.click();
            await delay(5000);

            var v = document.querySelector('video');
            if (!v) {
                console.log('  ❌ 无视频，标记跳过');
                var vm2 = getVm();
                if (vm2 && vm2.selectedLesson) vm2.selectedLesson.isComplete = true;
                await delay(1000);
                continue;
            }
            v.muted = true;

            await waitLessonComplete(cur.el);
            console.log('  ✅ ' + cur.name.slice(0, 15));
            await delay(2000);
        }
    }

    async function learnAllCourses() {
        console.log('🏠 回到课程列表...');
        await goToCourseList();

        var courses = getCourseList();
        console.log('📚 共 ' + courses.length + ' 门课程: ' + courses.join('、'));
        if (courses.length === 0) { console.log('❌ 无课程'); return; }

        for (var ci = 0; ci < courses.length; ci++) {
            var name = courses[ci];
            console.log('\n' + '='.repeat(50));
            console.log('📖 课程 [' + (ci+1) + '/' + courses.length + ']: ' + name);
            console.log('='.repeat(50));

            if (!isOnCourseList()) await goToCourseList();
            try {
                await enterCourse(name);
            } catch(e) {
                console.log('  ❌ 进入失败: ' + e);
                continue;
            }

            await learnCurrentCourse();

            if (ci < courses.length - 1) {
                console.log('\n📚 返回课程列表...');
            }
        }

        console.log('\n' + '🎉'.repeat(10));
        console.log('🎉 全部 ' + courses.length + ' 门课程学习完成！');
        console.log('🎉'.repeat(10));
    }

    function detectPage(cb) {
        if (isOnCourseList()) { cb('courseList'); return; }
        if (isOnLessonPage()) { cb('lessonPage'); return; }
        var ci = setInterval(function() {
            if (isOnCourseList()) { clearInterval(ci); cb('courseList'); }
            else if (isOnLessonPage()) { clearInterval(ci); cb('lessonPage'); }
        }, 1000);
    }

    function createButton(text, onClick) {
        var btn = document.createElement('button');
        btn.textContent = text;
        btn.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;padding:20px 40px;font-size:24px;background:#07c;color:#fff;border:none;border-radius:12px;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,0.3);';
        document.body.appendChild(btn);
        btn.onclick = onClick;
        return btn;
    }

    detectPage(function(pageType) {
        if (pageType === 'courseList') {
            var courses = getCourseList();
            var btn = createButton('📚 开始学习全部 ' + courses.length + ' 门课程', async function() {
                btn.remove();
                setTimeout(learnAllCourses, 500);
            });
        } else {
            var btn = createButton('🏠 先返回课程列表', async function() {
                btn.remove();
                await goToCourseList();
                var courses = getCourseList();
                var btn2 = createButton('📚 开始学习全部 ' + courses.length + ' 门课程', async function() {
                    btn2.remove();
                    setTimeout(learnAllCourses, 500);
                });
            });
        }
    });
})();
