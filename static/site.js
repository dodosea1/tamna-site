/* ORN Studio 사이트 동작. 라이브러리 없음.
   이 파일이 없어도(스크립트 꺼짐) 모든 글과 링크는 보인다. 숨기는 CSS는 html.js 아래에서만 걸린다. */
(function () {
  'use strict';
  var doc = document;
  function all(selector, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(selector)); }

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

  /* 휴대폰 메뉴 */
  var toggle = doc.querySelector('.menu-toggle');
  var nav = doc.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.textContent = open ? '닫기' : '메뉴';
    });
  }

  /* 머리띠: 조금 내려가면 바탕을 채운다. */
  var header = doc.querySelector('.site-header');
  if (header) {
    var onScroll = function () { header.classList.toggle('scrolled', window.scrollY > 40); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* 마지막 기록 날짜를 "오늘 / 어제 / N일 전"으로. 기록에는 날짜만 있어 한국 시간의 날짜끼리 뺀다. */
  var today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  all('time[data-rel]').forEach(function (t) {
    var days = Math.round((Date.parse(today) - Date.parse(t.getAttribute('datetime'))) / 86400000);
    if (isNaN(days) || days < 0) { return; }
    t.title = t.textContent;
    t.textContent = days === 0 ? '오늘' : (days === 1 ? '어제' : days + '일 전');
  });

  /* 올라오며 나타나기. 이미 화면에 있는 것은 숨기지 않는다(첫 화면이 깜박이지 않게). */
  var revealTargets = all('.game-card, .log-list li, .now-block, .follow-box');
  if (motionOK && canObserve) {
    var revealer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('in'); revealer.unobserve(entry.target); }
      });
    }, { threshold: 0.15 });
    revealTargets.forEach(function (el) {
      var box = el.getBoundingClientRect();
      if (box.top < window.innerHeight && box.left < window.innerWidth) { return; }
      el.classList.add('reveal');
      revealer.observe(el);
    });
  }

  /* 영상: 카드 미리보기(.card-video)와 게임 화면(.play-video).
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
      if (!next || pausedByUser.indexOf(next) !== -1) { return; }
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
  /* 움직임 줄이기·데이터 절약: 카드 영상은 포스터 그대로(카드 누름은 링크 그대로),
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
