/* ORN Studio 사이트 동작. 라이브러리 없음.
   이 파일이 없어도(스크립트 꺼짐) 모든 글과 링크는 보인다. 숨기는 CSS는 html.js 아래에서만 걸린다. */
(function () {
  'use strict';
  var doc = document;
  var root = doc.documentElement;
  function all(selector, from) { return Array.prototype.slice.call((from || doc).querySelectorAll(selector)); }

  /* 움직임을 줄이라는 설정이거나 데이터 절약 모드면 저절로 움직이거나 영상을 받지 않는다. */
  var reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var motionOK = !reduced && !saveData;
  var canObserve = 'IntersectionObserver' in window;

  /* 메일 주소: 수집 봇을 피해 스크립트로 조립한다. */
  all('.email').forEach(function (e) { e.textContent = e.dataset.u + '@' + e.dataset.d; });

  /* 복사 버튼(후원 계좌 등) */
  all('.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var label = b.textContent;
      navigator.clipboard.writeText(b.dataset.copy).then(function () {
        b.textContent = '복사했습니다';
        setTimeout(function () { b.textContent = label; }, 2000);
      });
    });
  });

  /* 메뉴: 휴대폰에서는 화면 전체를 덮는 목록. Escape나 메뉴 안 링크를 누르면 닫힌다. */
  var toggle = doc.querySelector('.menu-toggle');
  var nav = doc.getElementById('site-nav');
  if (toggle && nav) {
    var behind = all('main, .site-footer');
    var setMenu = function (open) {
      nav.classList.toggle('open', open);
      root.classList.toggle('menu-open', open);
      /* 메뉴가 덮고 있는 동안 뒤의 본문과 꼬리는 초점도 읽기도 받지 않는다 */
      behind.forEach(function (el) { el.inert = open; });
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
      toggle.textContent = open ? '닫기' : '메뉴';
    };
    toggle.addEventListener('click', function () { setMenu(!nav.classList.contains('open')); });
    doc.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) { setMenu(false); toggle.focus(); }
    });
    nav.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('a')) { setMenu(false); } });
  }

  /* 머리 바탕: 병풍 폭 위(k-home, k-game)에서는 투명, 한지 구간에 들어서면 먹 바탕 띠(solid).
     한지 읽는 페이지(k-paper)는 CSS가 처음부터 채운다. */
  var header = doc.querySelector('.site-header');
  var firstPaper = doc.querySelector('.paper');
  var overPanels = doc.body.classList.contains('k-home') || doc.body.classList.contains('k-game');
  if (header && firstPaper && overPanels) {
    var onScroll = function () { header.classList.toggle('solid', firstPaper.getBoundingClientRect().top <= header.offsetHeight); };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    window.addEventListener('load', onScroll);
    onScroll();
  }

  /* 마지막 기록 날짜를 "오늘 / 어제 / N일 전"으로. 기록에는 날짜만 있어 한국 시간의 날짜끼리 뺀다. */
  var today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  all('time[data-rel]').forEach(function (t) {
    var days = Math.round((Date.parse(today) - Date.parse(t.getAttribute('datetime'))) / 86400000);
    if (isNaN(days) || days < 0) { return; }
    t.title = t.textContent;
    /* "이번 주 기록 N개"는 빌드 때 센 값이다. 마지막 기록이 7일 넘게 지났으면 맞지 않으니 지운다. */
    if (days >= 7 && t.parentNode) { all('[data-week]', t.parentNode).forEach(function (w) { w.parentNode.removeChild(w); }); }
    t.textContent = days === 0 ? '오늘' : (days === 1 ? '어제' : days + '일 전');
  });

  /* 병풍 폭: 화면 가운데에 걸친 폭에 in(세로 제목과 도장이 찍히듯 나타남, 한 번만)을 붙이고 넘김 점을 옮긴다.
     화면 감시(IntersectionObserver)에 기대지 않고 스크롤 위치로 직접 본다. 폭은 많아야 몇 개다.
     움직임을 줄이면 모든 폭을 처음부터 in으로 둔다. */
  var panels = all('.panel');
  var dots = all('.dots i');
  if (!motionOK) { panels.forEach(function (p) { p.classList.add('in'); }); }
  var checkPanels = function () {
    var middle = window.innerHeight / 2;
    var centered = null;
    panels.forEach(function (p) {
      var box = p.getBoundingClientRect();
      if (box.top < window.innerHeight * 0.75 && box.bottom > window.innerHeight * 0.25) { p.classList.add('in'); }
      if (box.top <= middle && box.bottom > middle) { centered = p; }
    });
    dots.forEach(function (d) { d.classList.toggle('on', !!centered && d.getAttribute('data-for') === centered.id); });
  };
  if (panels.length) {
    var queued = false;
    var queueCheck = function () {
      if (queued) { return; }
      queued = true;
      (window.requestAnimationFrame || setTimeout)(function () { queued = false; checkPanels(); });
    };
    window.addEventListener('scroll', queueCheck, { passive: true });
    window.addEventListener('resize', queueCheck, { passive: true });
    window.addEventListener('load', checkPanels);
    /* 이 파일이 여기까지 돌았다는 표시. 폭의 세로 제목·도장을 들어올 때까지 숨기는 CSS는 이 표시가 있을 때만 걸린다.
       바로 다음 줄에서 지금 보이는 폭에 in을 붙이므로, 제목이 숨겨진 채 남지 않는다. */
    root.classList.add('ready');
    checkPanels();
  }

  /* 영상: 폭에 끼운 미리보기(.card-video)와 게임 화면(.play-video).
     처음에는 포스터 그림만 있다. 화면에 반 넘게 들어온 영상 가운데 가장 많이 보이는 하나만 받아서 재생한다. */
  var cardVideos = all('video.card-video[data-src]');
  var playVideos = all('video.play-video');
  if (motionOK && canObserve) {
    var seen = [];   /* { video, ratio } */
    var current = null;
    var pausedByUser = [];
    var pick = function () {
      var best = null;
      seen.forEach(function (s) { if (s.ratio >= 0.5 && (!best || s.ratio > best.ratio)) { best = s; } });
      var next = best ? best.video : null;
      if (current && current !== next) { current.pause(); }
      current = next;
      if (!next || doc.hidden || pausedByUser.indexOf(next) !== -1) { return; }
      if (!next.getAttribute('src') && next.dataset.src) { next.src = next.dataset.src; }
      var started = next.play();
      if (started && started.catch) { started.catch(function () { /* 자동 재생이 막힌 브라우저: 포스터 그대로 */ }); }
    };
    var watcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        seen.forEach(function (s) { if (s.video === entry.target) { s.ratio = entry.isIntersecting ? entry.intersectionRatio : 0; } });
      });
      pick();
    }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
    var startWatching = function () {
      cardVideos.concat(playVideos).forEach(function (v) { seen.push({ video: v, ratio: 0 }); watcher.observe(v); });
    };
    /* 다른 탭으로 가면 멈추고, 돌아오면 다시 고른다. */
    doc.addEventListener('visibilitychange', function () { if (doc.hidden) { if (current) { current.pause(); } } else { pick(); } });
    /* 게임 화면 영상: 저절로 재생하므로 조작 막대를 떼고, 누르면 멈춤/재생. */
    playVideos.forEach(function (v) {
      v.controls = false;
      v.tabIndex = 0;
      v.title = '누르면 멈추고, 다시 누르면 재생합니다';
      var flip = function () {
        var at = pausedByUser.indexOf(v);
        if (v.paused) { if (at !== -1) { pausedByUser.splice(at, 1); } v.play(); }
        else { if (at === -1) { pausedByUser.push(v); } v.pause(); }
      };
      v.addEventListener('click', flip);
      v.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } });
    });
    /* 첫 화면 그리기와 겨루지 않게, 페이지가 다 뜬 뒤에 지켜보기 시작한다. */
    if (doc.readyState === 'complete') { startWatching(); } else { window.addEventListener('load', startWatching); }
  }
  /* 움직임 줄이기·데이터 절약: 폭의 미리보기 영상은 받지 않고(포스터 그대로),
     게임 화면 영상은 조작 막대(HTML의 controls)를 눌러야만 받아서 재생한다. */

  /* 개발 중 화면 여러 장을 천천히 겹쳐 바꾼다. 움직임을 줄이면 첫 장만. */
  if (motionOK) {
    all('[data-slides]').forEach(function (box) {
      var pics = all('img', box);
      if (pics.length < 2) { return; }
      var at = 0;
      var visible = !canObserve;
      if (canObserve) {
        new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; }).observe(box);
      }
      setInterval(function () {
        if (!visible || doc.hidden) { return; }
        var next = (at + 1) % pics.length;
        if (!pics[next].complete) { return; }   /* 다음 그림을 아직 못 받았으면 기다린다 */
        pics[at].classList.remove('on');
        pics[next].classList.add('on');
        at = next;
      }, 4000);
    });
  }
})();
