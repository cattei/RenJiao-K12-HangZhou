/* 首页：统计、学科卡片、年级入口全部从 data/*.json 实时计算，不写死数量。
   2026-11-05：以线上 10 学科版本为基线重做视觉层，保留全部学科逻辑与本机盲区。 */
(function () {
  'use strict';
  var raw = location.hash.replace(/^#/, '');
  try { raw = decodeURIComponent(raw); } catch (e) { /* 保持原样 */ }
  if (/^(?:cnm|cne|cnp|cnc|cns|cnd|cnh|cng|cnb|cnk)_[A-Za-z0-9]+$/.test(raw)) return;

  var CN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
  var KEYS = ['math', 'chinese', 'science', 'morality', 'history', 'geography', 'biology', 'chemistry', 'english', 'physics'];
  var SUBJECTS = {
    math:      { name: '数学',       color: '#2AA88C', chip: '小学 → 高中 · 十科同步',               demo: 'diagnose/?target=cnm_221&demo=1', desc: '配方法' },
    chinese:   { name: '语文',       color: '#FF7A9C', chip: '小学一至六年级 · 统编版',            demo: 'diagnose/?subject=chinese&grade=' + encodeURIComponent('一上') + '&demo=1', desc: '一年级上册语文' },
    science:   { name: '科学',       color: '#22B8CF', chip: '小学一至六年级 · 教科版',            demo: 'diagnose/?subject=science&grade=' + encodeURIComponent('一上') + '&demo=1', desc: '一年级上册科学' },
    morality:  { name: '道德与法治', color: '#FB8B5C', chip: '小学一至六年级 · 统编版',            demo: 'diagnose/?subject=morality&grade=' + encodeURIComponent('一上') + '&demo=1', desc: '一年级上册道德与法治' },
    history:   { name: '历史',       color: '#A78BFA', chip: '初中七至九年级 · 统编版',            demo: 'diagnose/?subject=history&grade=' + encodeURIComponent('七上') + '&demo=1', desc: '七年级上册历史' },
    geography: { name: '地理',       color: '#34B57A', chip: '初中七至八年级 · 人教版',            demo: 'diagnose/?subject=geography&grade=' + encodeURIComponent('七上') + '&demo=1', desc: '七年级上册地理' },
    biology:   { name: '生物',       color: '#8CC63F', chip: '初中七至八年级 · 人教版',            demo: 'diagnose/?subject=biology&grade=' + encodeURIComponent('七上') + '&demo=1', desc: '七年级上册生物' },
    chemistry: { name: '化学',       color: '#EC4899', chip: '初中九年级 · 人教版',                 demo: 'diagnose/?subject=chemistry&grade=' + encodeURIComponent('九上') + '&demo=1', desc: '九年级上册化学' },
    english:   { name: '英语',       color: '#6C7BF2', chip: '三年级到高中 · 英语',                 demo: 'diagnose/?subject=english&grade=' + encodeURIComponent('四上') + '&demo=1', desc: '四年级上册英语' },
    physics:   { name: '物理',       color: '#F5A623', chip: '初中八、九年级 · 高中必修与选择性必修', demo: 'diagnose/?subject=physics&grade=' + encodeURIComponent('八上') + '&demo=1', desc: '八年级上册物理' }
  };
  var ID_PREFIX = { math: 'cnm_', english: 'cne_', physics: 'cnp_', chinese: 'cnc_', science: 'cns_', morality: 'cnd_', history: 'cnh_', geography: 'cng_', biology: 'cnb_', chemistry: 'cnk_' };
  var STD_PREFIX = { math: 'cms-', english: 'ces-', physics: 'cps-', chinese: 'ccs-', science: 'css-', morality: 'cds-', history: 'chs-', geography: 'cgs-', biology: 'cbs-', chemistry: 'cks-' };

  var subjectParam = new URLSearchParams(location.search).get('subject');
  var subject = SUBJECTS[subjectParam] ? subjectParam : 'math';
  var info = SUBJECTS[subject];

  function withSubject(href) {
    if (subject === 'math' || !href || href.indexOf('subject=') >= 0 || href.indexOf('http') === 0) return href;
    return href + (href.indexOf('?') >= 0 ? '&' : '?') + 'subject=' + subject;
  }
  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) node.textContent = value;
  }
  function fail(message) {
    var box = document.getElementById('load-error');
    if (!box) return;
    box.hidden = false;
    box.textContent = message;
  }

  /* ---- 学科切换：类、标题、文案、链接、高亮卡片 ---- */
  KEYS.forEach(function (key) {
    document.body.classList.toggle('subject-' + key, key === subject && key !== 'math');
  });
  document.querySelectorAll('.subject-link').forEach(function (link) {
    var on = link.getAttribute('data-subject') === subject;
    link.classList.toggle('on', on);
    if (on) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('.site-nav a:not(.subject-link), a.brand').forEach(function (link) {
    var href = link.getAttribute('href');
    var next = withSubject(href);
    if (next && next !== href) link.setAttribute('href', next);
  });
  document.querySelectorAll('.subject-card[data-subject]').forEach(function (card) {
    var on = card.getAttribute('data-subject') === subject;
    card.classList.toggle('is-current', on);
    if (on) card.setAttribute('aria-current', 'true');
    else card.removeAttribute('aria-current');
  });

  document.title = (subject === 'math' ? '' : info.name + ' · ') + '知识图谱 · 杭州 K12 同步学习';
  setText('hero-chip-text', info.chip);
  setText('current-subject-name', '当前学科 · ' + info.name);
  var currentDot = document.getElementById('current-subject-dot');
  if (currentDot) currentDot.style.background = info.color;
  var heroPrimary = document.querySelector('.hero-actions a.btn-primary');
  var heroBrowse = document.querySelector('.hero-actions a.btn:not(.btn-primary)');
  if (heroPrimary) heroPrimary.setAttribute('href', withSubject('diagnose/'));
  if (heroBrowse) heroBrowse.setAttribute('href', withSubject('explore/'));
  var demoLink = document.getElementById('demo-link');
  if (demoLink) demoLink.setAttribute('href', info.demo);
  var demoDesc = document.querySelector('.final-cta p');
  if (demoDesc) demoDesc.textContent = '先看一遍演示：' + info.desc + '。两分钟走完一次完整的答错回溯与路径生成。';

  /* ---- 本机盲区汇总（线上原有功能，原样保留） ---- */
  function renderBlindHome(allTopics) {
    var box = document.getElementById('blind-home');
    var list = document.getElementById('blind-home-list');
    var actions = document.getElementById('blind-home-actions');
    if (!box || !list || !actions || !window.CnmBlind) return;
    var nameOf = {};
    (allTopics || []).forEach(function (t) { nameOf[t.id] = t.name; });
    var rows = window.CnmBlind.list({ subject: subject, limit: 8 });
    if (!rows.length) {
      box.hidden = true;
      list.replaceChildren();
      actions.replaceChildren();
      return;
    }
    box.hidden = false;
    list.replaceChildren();
    rows.forEach(function (row) {
      var li = document.createElement('li');
      li.className = 'blind-home-item';
      var name = document.createElement('a');
      name.className = 'blind-home-name';
      name.href = window.CnmBlind.diagnoseHref([row.id], row.subject || subject);
      name.textContent = nameOf[row.id] || row.id;
      li.appendChild(name);
      var meta = document.createElement('span');
      meta.className = 'blind-home-meta';
      var bits = [row.status === 'weak' ? (row.root ? '根因' : '薄弱') : '不稳'];
      if (row.wrongs) bits.push('答错 ' + row.wrongs + ' 次');
      meta.textContent = bits.join(' · ');
      li.appendChild(meta);
      list.appendChild(li);
    });
    actions.replaceChildren();
    var cur = window.CnmChildren && window.CnmChildren.current && window.CnmChildren.current();
    var all = document.createElement('a');
    all.className = 'btn';
    all.href = window.CnmBlind.historyHref(cur && cur.id, 'children/');
    all.textContent = '查看全部盲区';
    actions.appendChild(all);
    var weakIds = rows.filter(function (r) { return r.status === 'weak'; }).slice(0, 5).map(function (r) { return r.id; });
    if (weakIds.length) {
      var re = document.createElement('a');
      re.className = 'btn btn-primary';
      re.href = window.CnmBlind.diagnoseHref(weakIds, subject);
      re.textContent = '再测本页薄弱点';
      actions.appendChild(re);
    }
  }

  Promise.all([
    fetch('data/topics.json'),
    fetch('data/dependencies.json'),
    fetch('data/questions.json'),
    fetch('data/cn-curriculum-standards.json')
  ]).then(function (responses) {
    responses.forEach(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
    });
    return Promise.all(responses.map(function (response) { return response.json(); }));
  }).then(function (data) {
    var allTopics = data[0];
    var allDeps = data[1];
    var allQuestions = data[2];
    var standards = data[3];
    if (!Array.isArray(allTopics) || !Array.isArray(allDeps) || !Array.isArray(allQuestions)) {
      throw new Error('数据格式无法识别');
    }
    var allItems = standards && Array.isArray(standards.items) ? standards.items : [];

    function subjectOfId(id) {
      id = String(id || '');
      for (var i = 0; i < KEYS.length; i++) {
        if (id.indexOf(ID_PREFIX[KEYS[i]]) === 0 && KEYS[i] !== 'math') return KEYS[i];
      }
      return 'math';
    }
    function subjectOfStd(id) {
      id = String(id || '');
      for (var i = 0; i < KEYS.length; i++) {
        if (id.indexOf(STD_PREFIX[KEYS[i]]) === 0 && KEYS[i] !== 'math') return KEYS[i];
      }
      return 'math';
    }

    /* 十科合计（stat-grid） */
    setText('n-topics', String(allTopics.length));
    setText('n-edges', String(allDeps.length));
    setText('n-questions', String(allQuestions.length));
    setText('n-standards', String(allItems.length));

    /* 十张学科卡片的数字 */
    KEYS.forEach(function (key) {
      var count = allTopics.filter(function (t) { return (t.subject || subjectOfId(t.id)) === key; }).length;
      var questions = allQuestions.filter(function (q) { return (q.subject || subjectOfId(q.topicId)) === key; }).length;
      var c = document.querySelector('[data-subject-count="' + key + '"]');
      var q = document.querySelector('[data-subject-questions="' + key + '"]');
      if (c) c.textContent = String(count);
      if (q) q.textContent = String(questions);
    });

    /* 当前学科统计（原有按学科筛选逻辑，保留在说明行） */
    var curTopics = allTopics.filter(function (t) { return (t.subject || subjectOfId(t.id)) === subject; });
    var curDeps = allDeps.filter(function (e) { return subjectOfId(e.topicId) === subject; });
    var curQuestions = allQuestions.filter(function (q) { return subjectOfId(q.topicId) === subject; });
    var curItems = allItems.filter(function (i) { return subjectOfStd(i.id) === subject; });
    var note = document.getElementById('stat-current');
    if (note) {
      note.textContent = '当前学科 · ' + info.name + '：' + curTopics.length + ' 个知识点 · ' +
        curDeps.length + ' 条先修边 · ' + curQuestions.length + ' 道题 · ' + curItems.length + ' 条课标条目。';
    }

    /* ---- 年级入口：按小学 / 初中 / 高中三段生成，保留线上各学科范围 ---- */
    var grades = document.getElementById('grades');
    if (!grades) return;
    grades.replaceChildren();
    grades.removeAttribute('aria-busy');

    var wantPhysics = subject === 'physics';
    var wantEnglish = subject === 'english';
    var wantChinese = subject === 'chinese' || subject === 'science' || subject === 'morality';
    var wantHistory = subject === 'history';
    var wantGeography = subject === 'geography';
    var wantBiology = subject === 'biology';
    var wantChemistry = subject === 'chemistry';
    var groups = [
      { key: 'primary', label: '小学', cards: [] },
      { key: 'junior', label: wantChemistry ? '初中化学' : (wantPhysics ? '初中物理' : '初中'), cards: [] },
      { key: 'senior', label: '高中', cards: [] }
    ];

    function push(stage, grade, title, href) {
      var count = curTopics.filter(function (topic) { return topic.grade === grade; }).length;
      groups.forEach(function (group) {
        if (group.key === stage) group.cards.push({ title: title, count: count, href: href });
      });
    }
    function gradeHref(g) {
      return subject !== 'math' ? 'explore/?subject=' + subject + '&grade=' + g : 'explore/?grade=' + g;
    }
    var from = wantPhysics ? 8 : (wantEnglish ? 3 : (wantChemistry ? 9 : (wantHistory || wantGeography || wantBiology ? 7 : 1)));
    var to = wantChinese ? 6 : (wantChemistry ? 9 : (wantGeography || wantBiology ? 8 : 9));
    for (var g = from; g <= to; g++) {
      push(g <= 6 ? 'primary' : 'junior', g, CN[g] + '年级', gradeHref(g));
    }
    if (wantPhysics) {
      [[10, '必修一'], [11, '必修二'], [12, '必修三'], [13, '选必一'], [14, '选必二'], [15, '选必三']]
        .forEach(function (pair) { push('senior', pair[0], pair[1], gradeHref(pair[0])); });
    } else if (wantEnglish) {
      [[10, '必修一'], [11, '必修二'], [12, '必修三'], [13, '选必一'], [14, '选必二'], [15, '选必三'], [16, '选必四']]
        .forEach(function (pair) { push('senior', pair[0], pair[1], gradeHref(pair[0])); });
    } else if (!wantChinese && !wantHistory && !wantGeography && !wantBiology && !wantChemistry) {
      [[10, '高一'], [11, '高二'], [12, '选必一'], [13, '选必二'], [14, '选必三']]
        .forEach(function (pair) { push('senior', pair[0], pair[1], gradeHref(pair[0])); });
    }

    var RANGE = {
      primary: wantEnglish ? '三 – 六年级' : '一 – 六年级',
      junior: wantChemistry ? '九年级' : (wantPhysics ? '八 – 九年级' : (wantGeography || wantBiology ? '七 – 八年级' : '七 – 九年级')),
      senior: '必修 + 选必'
    };
    groups.forEach(function (group) {
      if (!group.cards.length) return;
      var total = group.cards.reduce(function (sum, card) { return sum + card.count; }, 0);
      var wrap = document.createElement('div');
      wrap.className = 'grade-group grade-group--' + group.key;
      wrap.setAttribute('data-stage', group.key);
      var label = document.createElement('div');
      label.className = 'grade-group__label';
      var badge = document.createElement('span');
      badge.className = 'grade-group__badge';
      badge.textContent = group.label;
      var range = document.createElement('span');
      range.className = 'grade-group__range';
      range.textContent = RANGE[group.key] + ' · ' + total + ' 个知识点';
      label.append(badge, range);
      var cards = document.createElement('div');
      cards.className = 'grade-group__cards';
      group.cards.forEach(function (card) {
        var link = document.createElement('a');
        link.className = 'grade-card';
        link.href = card.href;
        link.textContent = card.title + ' · ' + card.count;
        cards.append(link);
      });
      wrap.append(label, cards);
      grades.append(wrap);
    });

    /* 学段筛选（纯展示层交互，不改变数据） */
    document.querySelectorAll('.stage-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var stage = chip.getAttribute('data-stage');
        document.querySelectorAll('.stage-chip').forEach(function (item) {
          item.classList.toggle('on', item === chip);
        });
        document.querySelectorAll('.grade-group').forEach(function (group) {
          group.hidden = stage !== 'all' && group.getAttribute('data-stage') !== stage;
        });
      });
    });

    renderBlindHome(allTopics);
  }).catch(function (error) {
    fail('数据没有加载成功（' + (error && error.message ? error.message : error) + '）。请在项目根目录运行 python3 -m http.server 8000，再用浏览器打开，不要直接双击 html 文件。');
  });
})();
