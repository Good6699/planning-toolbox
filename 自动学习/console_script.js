(async function() {
    // 1. 获取 Vue 数据
    let vm = null;
    let el = document.querySelector('a.lesson.active');
    while (el) { if (el.__vue__) { vm = el.__vue__; break; } el = el.parentElement; }
    if (!vm) return console.log('❌ 取不到 Vue 实例');

    const lessons = vm.lessons || vm.lessonList || [];
    const unlearned = lessons.filter(l => !l.isComplete && l.mediaUrl);
    console.log(`📚 课程: ${unlearned.length} 个未学完`);

    if (unlearned.length === 0) return console.log('✅ 全部已学完!');

    // 2. 创建隐藏视频容器
    let oldContainer = document.querySelector('div[style*="top:-9999px"]');
    if (oldContainer) oldContainer.remove();

    const container = document.createElement('div');
    container.style.cssText = 'position:fixed;top:-9999px;left:-9999px;z-index:9999;';
    document.body.appendChild(container);

    const videos = [];
    for (const l of unlearned) {
        const v = document.createElement('video');
        v.src = l.mediaUrl;
        v.playbackRate = 2;
        v.muted = true;
        container.appendChild(v);
        v.play().catch(() => {});
        videos.push(v);
        console.log(`  ▶ ${l.lessonName} (~${Math.round((v.duration||87)/2)}s)`);
    }

    // 3. 进度监控 + 自动上报
    const reported = new Set();
    const total = unlearned.length;

    const intervalId = setInterval(() => {
        let doneCount = 0;
        videos.forEach((v, i) => {
            if (!v.ended) return;
            doneCount++;
            if (reported.has(i)) return;

            // 切换 selectedLesson 并调用 achieve 上报
            const orig = vm.selectedLesson;
            vm.selectedLesson = unlearned[i];
            try { vm.achieve(); } catch(e) {}
            vm.selectedLesson = orig;
            reported.add(i);
            console.log(`  [${reported.size}/${total}] ✅ ${unlearned[i].lessonName}`);
        });

        // 未完成的视频进度
        videos.forEach((v, i) => {
            if (v.ended) return;
            console.log(`  [${i+1}] ▶ ${unlearned[i].lessonName.slice(0,12)} ${Math.round(v.currentTime)}s / ${Math.round(v.duration)}s`);
        });

        if (reported.size >= total || doneCount >= total) {
            clearInterval(intervalId);
            console.log(`\n🎉 全部完成! ${reported.size}/${total} 刷新页面查看效果`);
        }
    }, 30000);

    console.log('\n⏳ 每30秒自动报告进度...');
})();
