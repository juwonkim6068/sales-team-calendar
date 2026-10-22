<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>업무관리 시스템</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root {
  --bg: #f5f7fb;
  --card: #ffffff;
  --line: #e9edf3;
  --ink: #1b1f2a;
  --sub: #5f6675;
  --muted: #9aa1ae;
  --blue: #1f6bff;
  --blue-soft: #e8f0ff;
  --green: #22c06b;
  --green-soft: #e3f7ec;
  --orange: #ffa51f;
  --orange-soft: #fff3df;
  --red: #f04848;
  --red-soft: #fde8e8;
  --purple: #9a7cf2;
  --teal: #2ec4b6;
  --gray-bar: #b8c2d1;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--bg); color: var(--ink); font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif; font-size: 14px; letter-spacing: -0.01em; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
svg { display: block; }

/* ---------- 헤더 ---------- */
.top { height: 64px; background: var(--card); border-bottom: 1px solid var(--line); display: grid; grid-template-columns: 232px 1fr auto; align-items: center; position: sticky; top: 0; z-index: 10; }
.logo { display: flex; align-items: center; gap: 12px; padding-left: 24px; font-size: 17px; font-weight: 700; }
.logo i { width: 28px; height: 28px; border-radius: 7px; background: var(--blue); display: grid; place-items: center; }
.gsearch { margin-left: 194px; width: 680px; max-width: calc(100% - 210px); height: 38px; background: #f2f4f8; border-radius: 8px; display: flex; align-items: center; gap: 10px; padding: 0 14px; color: var(--muted); }
.gsearch input { border: 0; background: none; outline: none; flex: 1; min-width: 0; }
.gsearch input::placeholder { color: var(--muted); }
.tools { display: flex; align-items: center; gap: 28px; padding-right: 28px; }
.bell { position: relative; background: none; border: 0; padding: 4px; color: var(--sub); }
.bell::after { content: ""; position: absolute; top: 3px; right: 3px; width: 8px; height: 8px; border-radius: 50%; background: var(--red); border: 2px solid var(--card); }
.me { display: flex; align-items: center; gap: 12px; }
.me b { display: block; font-size: 15px; font-weight: 600; }
.me small { color: var(--sub); font-size: 13px; }

.avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 600; font-size: 14px; flex: none; }
.avatar.sm { width: 24px; height: 24px; font-size: 11px; }

/* ---------- 레이아웃 ---------- */
.app { display: grid; grid-template-columns: 232px 1fr; min-height: calc(100vh - 64px); }
.side { background: var(--card); border-right: 1px solid var(--line); padding: 20px 0; display: flex; flex-direction: column; }
.side a { display: flex; align-items: center; gap: 14px; height: 46px; margin: 0 12px 3px; padding: 0 16px; border-radius: 8px; color: #343a46; text-decoration: none; font-size: 15px; font-weight: 500; position: relative; }
.side a:hover { background: #f4f6fa; }
.side a.on { background: var(--blue-soft); color: var(--blue); font-weight: 600; }
.side a.on::before { content: ""; position: absolute; left: -12px; top: 6px; bottom: 6px; width: 4px; border-radius: 0 3px 3px 0; background: var(--blue); }
.side a svg { color: currentColor; }
.side .bottom { margin-top: auto; border-top: 1px solid var(--line); margin-inline: 24px; padding-top: 20px; }
.side .bottom a { margin-inline: -12px; }

main { padding: 22px 16px 16px 20px; min-width: 0; }
.hello { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; padding-left: 6px; }
.hello h1 { margin: 0; font-size: 27px; font-weight: 700; letter-spacing: -0.03em; }
.hello p { margin: 6px 0 0; color: var(--sub); font-size: 15px; }
.hello .when { display: flex; align-items: center; gap: 28px; color: #343a46; font-size: 16px; padding-top: 10px; }
.hello .when span { display: flex; align-items: center; gap: 10px; }

.grid { display: grid; grid-template-columns: minmax(0, 1fr) 344px; gap: 16px; align-items: start; }
.left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.right { display: flex; flex-direction: column; gap: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; }

/* ---------- 상단 숫자 카드 ---------- */
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.stat { height: 106px; display: flex; align-items: center; gap: 22px; padding: 0 20px; }
.stat .ic { width: 70px; height: 70px; border-radius: 12px; display: grid; place-items: center; flex: none; }
.stat span { display: block; font-size: 15px; font-weight: 500; }
.stat b { font-size: 31px; font-weight: 700; letter-spacing: -0.02em; }
.stat b small { font-size: 14px; font-weight: 500; color: var(--sub); margin-left: 6px; }

/* ---------- 차트 ---------- */
.charts { display: grid; grid-template-columns: minmax(0, 432fr) minmax(0, 460fr); gap: 16px; }
.chart { height: 246px; padding: 18px 20px; }
.chart h2, .card h2 { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }
.donut-wrap { display: flex; align-items: center; gap: 40px; padding: 18px 10px 0 10px; }
.donut { position: relative; width: 166px; height: 166px; flex: none; }
.donut .c { position: absolute; inset: 0; display: grid; place-items: center; text-align: center; font-size: 17px; font-weight: 700; line-height: 1.35; }
.legend { display: flex; flex-direction: column; gap: 14px; flex: 1; }
.legend div { display: grid; grid-template-columns: 14px 1fr auto; align-items: center; gap: 8px; font-size: 15px; }
.legend i { width: 10px; height: 10px; border-radius: 50%; }
.legend b { font-weight: 600; font-size: 16px; }
.legend b small { font-weight: 500; font-size: 16px; }

.bars { position: relative; height: 158px; margin: 26px 0 0 30px; }
.bars .gl { position: absolute; left: 0; right: 0; height: 1px; background: #eef1f5; }
.bars .gl span { position: absolute; left: -30px; top: -8px; width: 20px; text-align: right; font-size: 13px; color: #4d5462; }
.bars .gl.base { background: #dfe4ec; }
.bars .cols { position: absolute; inset: 0 20px 0 10px; display: flex; justify-content: space-between; align-items: flex-end; }
.bars .col { width: 46px; position: relative; display: flex; flex-direction: column; align-items: center; }
.bars .col .v { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.bars .col .b { width: 46px; border-radius: 3px 3px 0 0; }
.bars .col .n { position: absolute; top: calc(100% + 8px); font-size: 13px; color: #4d5462; white-space: nowrap; }

/* ---------- 업무 목록 ---------- */
.tasks { padding: 14px 16px 6px 18px; }
.thead { display: flex; align-items: center; gap: 24px; margin-bottom: 14px; }
.thead h2 small { font-size: 16px; color: var(--sub); font-weight: 500; margin-left: 8px; }
.tabs { display: flex; gap: 8px; margin-left: 50px; }
.tabs button { height: 36px; padding: 0 18px; border-radius: 18px; border: 1px solid var(--line); background: var(--card); color: #4d5462; font-size: 14px; }
.tabs button.on { background: var(--blue-soft); border-color: #bcd2ff; color: var(--blue); font-weight: 600; }
.write { margin-left: auto; height: 36px; padding: 0 18px; border-radius: 7px; border: 0; background: var(--blue); color: #fff; font-weight: 600; display: flex; align-items: center; gap: 6px; font-size: 14px; }
.filters { display: grid; grid-template-columns: minmax(0, 1fr) 146px 146px 156px; gap: 12px; margin-bottom: 12px; }
.filters .s { height: 38px; border: 1px solid #dfe4ec; border-radius: 6px; display: flex; align-items: center; gap: 8px; padding: 0 12px; color: var(--muted); }
.filters .s input { border: 0; outline: none; flex: 1; min-width: 0; background: none; }
.filters .s input::placeholder { color: var(--muted); }
.filters .s.sel { color: #343a46; justify-content: space-between; }
.filters .s:nth-child(2) { margin-left: 16px; }
table { width: 100%; border-collapse: collapse; }
th { height: 36px; background: #f4f6f9; font-size: 13px; font-weight: 600; text-align: left; color: #343a46; }
th:first-child { border-radius: 6px 0 0 6px; }
th:last-child { border-radius: 0 6px 6px 0; }
td { height: 41px; border-bottom: 1px solid #eef1f5; font-size: 14px; }
td.p { color: #5f6675; font-size: 13px; }
td:first-child, th:first-child { width: 40px; padding-left: 10px; }
.chk { width: 17px; height: 17px; border: 1.5px solid #c9d0db; border-radius: 4px; display: block; }
.who { display: flex; align-items: center; gap: 10px; }
.pill { display: inline-block; height: 22px; line-height: 22px; padding: 0 9px; border-radius: 5px; font-size: 13px; font-weight: 500; }
.hi { background: var(--red-soft); color: var(--red); }
.mid { background: var(--orange-soft); color: #f08c00; }
.lo { background: #f1f3f6; color: #5f6675; }
.st-run { background: var(--blue-soft); color: var(--blue); }
.st-done { background: var(--green-soft); color: #1a9e57; }
.st-late { background: var(--red-soft); color: var(--red); }
td.late { color: var(--red); }
.dots { color: #5f6675; letter-spacing: 1px; text-align: center; font-weight: 700; }

/* ---------- 오른쪽: 미니 달력 ---------- */
.mini { padding: 16px 18px 12px 18px; }
.mini .h { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.mini .nav { display: flex; gap: 6px; align-items: center; }
.mini .nav button { width: 30px; height: 26px; border: 1px solid transparent; border-radius: 5px; background: none; display: grid; place-items: center; color: #343a46; }
.mini .nav button.bd { border-color: #dfe4ec; }
.mini .nav .today { width: auto; padding: 0 10px; border: 1px solid #bcd2ff; color: var(--blue); font-size: 13px; font-weight: 600; }
.cal { display: grid; grid-template-columns: repeat(7, 1fr); row-gap: 2px; text-align: center; }
.cal .w { font-size: 13px; color: #4d5462; height: 30px; line-height: 30px; }
.cal .d { height: 34px; display: grid; place-items: center; position: relative; font-size: 14px; color: #343a46; }
.cal .d.o { color: var(--muted); }
.cal .d.b { font-weight: 700; }
.cal .d.b::after { content: ""; position: absolute; bottom: 3px; width: 14px; height: 2px; background: #343a46; }
.cal .d.dot::after { content: ""; position: absolute; bottom: 2px; width: 4px; height: 4px; border-radius: 50%; background: var(--blue); }
.cal .d.t span { width: 36px; height: 36px; border-radius: 50%; background: var(--blue); color: #fff; display: grid; place-items: center; font-weight: 600; }

/* ---------- 다가오는 일정 ---------- */
.up { padding: 16px 18px 8px 18px; }
.sec-h { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.sec-h h2 small { font-size: 16px; font-weight: 500; color: var(--sub); margin-left: 12px; }
.more { color: var(--blue); font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 2px; }
.ev { display: grid; grid-template-columns: 44px 22px 1fr; padding: 10px 0 0; }
.ev .d { font-size: 14px; font-weight: 600; text-align: center; line-height: 1.45; }
.ev .d small { display: block; color: var(--sub); font-weight: 400; font-size: 13px; }
.ev .ln { position: relative; display: flex; justify-content: center; }
.ev .ln::before { content: ""; position: absolute; top: 18px; bottom: -10px; width: 1px; background: #e6eaf0; }
.ev:last-child .ln::before { display: none; }
.ev .ln i { width: 9px; height: 9px; border-radius: 50%; margin-top: 7px; position: relative; }
.ev .t { padding: 0 0 10px 4px; border-bottom: 1px solid #eef1f5; }
.ev:last-child .t { border-bottom: 0; }
.ev .t b { display: block; font-size: 15px; font-weight: 500; }
.ev .t small { color: var(--sub); font-size: 13px; }

/* ---------- 공지사항 ---------- */
.notice { padding: 16px 18px 6px 18px; }
.notice ul { list-style: none; margin: 0; padding: 0; }
.notice li { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid #eef1f5; font-size: 15px; }
.notice li:last-child { border-bottom: 0; }
.notice li small { color: var(--sub); font-size: 13px; flex: none; }

@media (max-width: 1440px) {
  .gsearch { margin-left: 40px; width: auto; max-width: 680px; }
  .donut-wrap { gap: 24px; padding-inline: 0; }
  .stat { gap: 14px; padding: 0 16px; }
  .stat .ic { width: 60px; height: 60px; }
  .tabs { margin-left: 8px; }
  .top { grid-template-columns: 200px 1fr auto; }
  .app { grid-template-columns: 200px 1fr; }
  .grid { grid-template-columns: minmax(0, 1fr) 300px; }
  .stat b { font-size: 26px; }
  .tabs button { padding: 0 12px; }
  .filters { grid-template-columns: minmax(0, 1fr) repeat(3, minmax(0, 140px)); }
  .filters .s:nth-child(2) { margin-left: 0; }
}
.me, .logo, .stat span, .legend div, th, td, .tabs button, .write, .thead h2, .filters .s, .bars .col .n { white-space: nowrap; }
.tablewrap { overflow-x: auto; }
table { min-width: 720px; }
@media (max-width: 1180px) {
  .grid { grid-template-columns: minmax(0, 1fr); }
  .charts { grid-template-columns: minmax(0, 1fr); }
  .right { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
}
@media (max-width: 900px) {
  .top { grid-template-columns: 1fr auto; }
  .gsearch, .me div { display: none; }
  .app { grid-template-columns: minmax(0, 1fr); }
  .side { display: none; }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hello { flex-direction: column; gap: 8px; }
  .hello .when { padding-top: 0; }
  .thead { flex-wrap: wrap; }
  .tabs { margin-left: 0; order: 3; width: 100%; overflow-x: auto; }
  .filters { grid-template-columns: 1fr 1fr; }
  .filters .s:first-child { grid-column: 1 / -1; }
  .filters .s:nth-child(2) { margin-left: 0; }
  .tablewrap { overflow-x: auto; }
  table { min-width: 820px; }
}
</style>
</head>
<body>

<header class="top">
  <div class="logo">
    <i><svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><rect x="3" y="3" width="8" height="8" rx="2"/><path d="M13 13h6a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-6z"/><path d="M11 11l3 3" stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg></i>
    업무관리 시스템
  </div>
  <label class="gsearch">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5" stroke-linecap="round"/></svg>
    <input placeholder="업무, 프로젝트, 담당자 등을 검색하세요.">
  </label>
  <div class="tools">
    <button class="bell" aria-label="알림"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg></button>
    <div class="me">
      <span class="avatar" style="background:#c98a6b">김</span>
      <div><b>김지은</b><small>마케팅팀</small></div>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
    </div>
  </div>
</header>

<div class="app">
  <nav class="side">
    <a href="#" class="on"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>대시보드</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.4 2.6a2 2 0 0 1 3 3L12 15l-4 1 1-4z"/></svg>업무 작성</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>업무 현황</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 10h18"/></svg>프로젝트</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/></svg>일정 관리</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></svg>보고서</a>
    <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/></svg>팀원 관리</a>
    <div class="bottom">
      <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>설정</a>
      <a href="#"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/></svg>도움말</a>
    </div>
  </nav>

  <main>
    <div class="hello">
      <div>
        <h1>김지은 님, 오늘도 좋은 하루하세요! 👋</h1>
        <p>현재 진행 중인 업무 6건이 있습니다.</p>
      </div>
      <div class="when">
        <span>2024년 5월 14일 (화)</span>
        <span><svg width="26" height="26" viewBox="0 0 24 24"><circle cx="10" cy="10" r="5.5" fill="#ffb31f"/><path d="M8 20h9a3.5 3.5 0 0 0 0-7 4.5 4.5 0 0 0-8.6 1.2A3 3 0 0 0 8 20z" fill="#dfe6f0"/></svg>맑음 22°C</span>
      </div>
    </div>

    <div class="grid">
      <div class="left">
        <div class="stats">
          <div class="card stat"><div class="ic" style="background:#e5efff"><svg width="34" height="38" viewBox="0 0 24 28"><path d="M3 4a3 3 0 0 1 3-3h9l6 6v17a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" fill="#2f7cff"/><path d="M8 13h8M8 17h8M8 21h5" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg></div><div><span>전체 업무</span><b>24<small>건</small></b></div></div>
          <div class="card stat"><div class="ic" style="background:#ddf6e8"><svg width="30" height="32" viewBox="0 0 20 22"><path d="M3 2.5v17a1 1 0 0 0 1.5.9l14-8.5a1 1 0 0 0 0-1.8l-14-8.5A1 1 0 0 0 3 2.5z" fill="#22c06b"/></svg></div><div><span>진행 중</span><b>6<small>건</small></b></div></div>
          <div class="card stat"><div class="ic" style="background:#fff1db"><svg width="38" height="38" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#ffa51f"/><path d="m7 12.5 3.2 3L17 9" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></div><div><span>완료</span><b>15<small>건</small></b></div></div>
          <div class="card stat"><div class="ic" style="background:#fde5e5"><svg width="38" height="38" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#f04848"/><path d="M12 6.5v7" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><circle cx="12" cy="17.3" r="1.5" fill="#fff"/></svg></div><div><span>지연</span><b>3<small>건</small></b></div></div>
        </div>

        <div class="charts">
          <div class="card chart">
            <h2>업무 진행 현황</h2>
            <div class="donut-wrap">
              <div class="donut">
                <svg width="166" height="166" viewBox="0 0 42 42" style="transform:rotate(-90deg)">
                  <circle cx="21" cy="21" r="15.915" fill="none" stroke="#22c06b" stroke-width="8.2" stroke-dasharray="62.5 37.5" stroke-dashoffset="0"/>
                  <circle cx="21" cy="21" r="15.915" fill="none" stroke="#2f7cff" stroke-width="8.2" stroke-dasharray="25 75" stroke-dashoffset="-62.5"/>
                  <circle cx="21" cy="21" r="15.915" fill="none" stroke="#f04848" stroke-width="8.2" stroke-dasharray="12.5 87.5" stroke-dashoffset="-87.5"/>
                </svg>
                <div class="c">총<br>24건</div>
              </div>
              <div class="legend">
                <div><i style="background:#22c06b"></i>완료<b>15 <small>(62%)</small></b></div>
                <div><i style="background:#2f7cff"></i>진행 중<b>6 <small>(25%)</small></b></div>
                <div><i style="background:#f04848"></i>지연<b>3 <small>(13%)</small></b></div>
              </div>
            </div>
          </div>

          <div class="card chart">
            <h2>부서별 업무 현황</h2>
            <div class="bars" id="bars"></div>
          </div>
        </div>

        <div class="card tasks">
          <div class="thead">
            <h2>업무 목록<small>24건</small></h2>
            <div class="tabs" id="tabs">
              <button class="on" data-f="all">전체 (24)</button>
              <button data-f="진행 중">진행 중 (6)</button>
              <button data-f="완료">완료 (15)</button>
              <button data-f="지연">지연 (3)</button>
            </div>
            <button class="write"><svg width="16" height="16" viewBox="0 0 24 24" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>업무 작성</button>
          </div>
          <div class="filters">
            <label class="s"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5" stroke-linecap="round"/></svg><input id="q" placeholder="업무명을 검색하세요."></label>
            <div class="s sel">전체 기간<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2.2"><path d="m6 9 6 6 6-6"/></svg></div>
            <div class="s sel">전체 담당자<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2.2"><path d="m6 9 6 6 6-6"/></svg></div>
            <div class="s sel">전체 상태<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#343a46" stroke-width="2.2"><path d="m6 9 6 6 6-6"/></svg></div>
          </div>
          <div class="tablewrap">
            <table>
              <thead><tr><th><span class="chk"></span></th><th style="width:30%">업무명</th><th>프로젝트</th><th>담당자</th><th>우선순위</th><th>상태</th><th>마감일</th><th style="width:40px"><span class="dots">···</span></th></tr></thead>
              <tbody id="rows"></tbody>
            </table>
          </div>
        </div>
      </div>

      <aside class="right">
        <div class="card mini">
          <div class="h">
            <h2>5월 일정</h2>
            <div class="nav">
              <button aria-label="이전 달"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m15 18-6-6 6-6"/></svg></button>
              <button class="bd" aria-label="다음 달"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m9 18 6-6-6-6"/></svg></button>
              <button class="today">오늘</button>
            </div>
          </div>
          <div class="cal" id="cal"></div>
        </div>

        <div class="card up">
          <div class="sec-h"><h2>다가오는 일정<small>4건</small></h2><a class="more" href="#">전체보기 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m9 18 6-6-6-6"/></svg></a></div>
          <div class="ev"><div class="d">5.15<small>(수)</small></div><div class="ln"><i style="background:#2f7cff"></i></div><div class="t"><b>신규 캠페인 기획안 제출</b><small>10:00 - 11:00 &nbsp;• 마케팅팀</small></div></div>
          <div class="ev"><div class="d">5.16<small>(목)</small></div><div class="ln"><i style="background:#22c06b"></i></div><div class="t"><b>업체 미팅</b><small>14:00 - 15:00 &nbsp;• 회의실 B</small></div></div>
          <div class="ev"><div class="d">5.17<small>(금)</small></div><div class="ln"><i style="background:#ffa51f"></i></div><div class="t"><b>홈페이지 리뉴얼 1차 완료</b><small>종일 &nbsp;• 개발팀</small></div></div>
          <div class="ev"><div class="d">5.22<small>(수)</small></div><div class="ln"><i style="background:#9a7cf2"></i></div><div class="t"><b>월간 운영 회의</b><small>10:00 - 11:00 &nbsp;• 전사</small></div></div>
        </div>

        <div class="card notice">
          <div class="sec-h"><h2>공지사항</h2><a class="more" href="#">전체보기 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m9 18 6-6-6-6"/></svg></a></div>
          <ul>
            <li>[안내] 5월 전사 워크숍 일정 안내<small>05.10</small></li>
            <li>[필독] 보안 정책 개정 안내<small>05.08</small></li>
            <li>[공지] 사내 시스템 점검 일정<small>05.01</small></li>
          </ul>
        </div>
      </aside>
    </div>
  </main>
</div>

<script>
/* 부서별 막대 차트 */
const depts = [["마케팅팀", 8, "#4f9bff"], ["기획팀", 6, "#a184f4"], ["개발팀", 5, "#33c9bb"], ["디자인팀", 3, "#ffb53d"], ["운영팀", 2, "#b8c2d1"]];
const H = 158, MAX = 10;
document.getElementById("bars").innerHTML =
  [0, 2, 4, 6, 8, 10].map(v => `<div class="gl${v === 0 ? " base" : ""}" style="top:${H - v / MAX * H}px"><span>${v}</span></div>`).join("") +
  `<div class="cols">${depts.map(([n, v, c]) => `<div class="col"><span class="v">${v}</span><div class="b" style="height:${v / MAX * H}px;background:${c}"></div><span class="n">${n}</span></div>`).join("")}</div>`;

/* 업무 목록 */
const avatarColor = { "김지은": "#c98a6b", "이준호": "#6b7a8f", "박수연": "#a7735a", "최민수": "#7d8796", "정하늘": "#b48366" };
const tasks = [
  ["신규 캠페인 기획안 작성", "브랜드 캠페인", "김지은", "높음", "진행 중", "2024-05-15"],
  ["홈페이지 리뉴얼 콘텐츠 검수", "홈페이지 리뉴얼", "이준호", "보통", "진행 중", "2024-05-17"],
  ["5월 마케팅 성과 리포트", "월간 리포트", "박수연", "높음", "완료", "2024-05-14"],
  ["업체 미팅 자료 준비", "파트너십", "최민수", "보통", "진행 중", "2024-05-16"],
  ["SNS 콘텐츠 디자인 요청", "브랜드 캠페인", "정하늘", "낮음", "지연", "2024-05-12"],
  ["서비스 개선 의견 정리", "내부 개선", "김지은", "보통", "완료", "2024-05-10"],
  ["경쟁사 리서치", "시장 조사", "이준호", "낮음", "진행 중", "2024-05-20"],
];
const pr = { "높음": "hi", "보통": "mid", "낮음": "lo" };
const st = { "진행 중": "st-run", "완료": "st-done", "지연": "st-late" };
let tab = "all";
function drawRows() {
  const q = document.getElementById("q").value.trim();
  document.getElementById("rows").innerHTML = tasks
    .filter(t => (tab === "all" || t[4] === tab) && (!q || t[0].includes(q)))
    .map(([title, proj, who, p, s, due]) => `<tr>
      <td><span class="chk"></span></td><td>${title}</td><td class="p">${proj}</td>
      <td><span class="who"><span class="avatar sm" style="background:${avatarColor[who]}">${who[0]}</span>${who}</span></td>
      <td><span class="pill ${pr[p]}">${p}</span></td><td><span class="pill ${st[s]}">${s}</span></td>
      <td class="${s === "지연" ? "late" : ""}">${due}</td><td class="dots">···</td></tr>`).join("");
}
document.getElementById("tabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  tab = b.dataset.f;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  drawRows();
});
document.getElementById("q").addEventListener("input", drawRows);
drawRows();

/* 미니 달력 (2024년 5월) */
const marks = { 9: "dot", 17: "dot", 22: "b", 29: "b" };
let cal = ["일", "월", "화", "수", "목", "금", "토"].map(w => `<div class="w">${w}</div>`).join("");
[28, 29, 30].forEach(d => cal += `<div class="d o">${d}</div>`);
for (let d = 1; d <= 31; d++) cal += d === 14 ? `<div class="d t"><span>14</span></div>` : `<div class="d ${marks[d] || ""}">${d}</div>`;
cal += `<div class="d o">1</div>`;
document.getElementById("cal").innerHTML = cal;
</script>
</body>
</html>
