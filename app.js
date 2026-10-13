/*
  jnwb dashboard renderer. Fills index.html from data.json, which the dashboard build writes.
  Plain ES2019 in one function scope: no build step, no framework. Every value comes from
  data.json. A null or absent section renders "Not recorded" in .empty, never a placeholder.
*/
(function () {
  'use strict';

  var DATA_URL = 'data.json';
  var THEME_KEY = 'jnwb-dashboard-theme';
  var THEMES = ['system', 'light', 'dark'];
  var NOT_RECORDED = 'Not recorded';
  var NONE_RECORDED = 'None recorded.';
  var MIDDOT = '·';
  var EN_DASH = '–';
  var UP = '▲';
  var DOWN = '▼';

  var systemDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  var theme = 'system';
  var tabs = [];
  var charts = [];
  var figureImages = [];

  // ---- values -------------------------------------------------------------

  function isMissing(value) {
    return value === null || value === undefined;
  }

  function isBlank(value) {
    return isMissing(value) || value === '';
  }

  // Walks a dotted path. A null or absent step anywhere gives undefined.
  function lookup(data, path) {
    var node = data;
    var keys = path.split('.');
    for (var i = 0; i < keys.length; i += 1) {
      if (isMissing(node) || typeof node !== 'object') {
        return undefined;
      }
      node = node[keys[i]];
    }
    return isMissing(node) ? undefined : node;
  }

  // Derived slots: values the page computes from the record, never typed in.
  var DERIVED = {
    'overview.python_range': derivePythonRange,
    'overview.verified_count': deriveVerifiedCount,
    'overview.ci_count': deriveCiCount
  };

  // pyproject lists a bare "Programming Language :: Python :: 3" besides the minor versions.
  // Only the minor versions bound the supported range.
  function derivePythonRange(data) {
    var classifiers = lookup(data, 'release.python');
    if (!Array.isArray(classifiers)) {
      return undefined;
    }
    var versions = [];
    classifiers.forEach(function (classifier) {
      var match = /\d+\.\d+/.exec(String(classifier));
      if (match && versions.indexOf(match[0]) === -1) {
        versions.push(match[0]);
      }
    });
    if (!versions.length) {
      return undefined;
    }
    var first = versions[0];
    var last = versions[versions.length - 1];
    return first === last ? first : first + EN_DASH + last;
  }

  function deriveVerifiedCount(data) {
    var functions = lookup(data, 'verified.functions');
    return Array.isArray(functions) ? functions.length : undefined;
  }

  function deriveCiCount(data) {
    var legs = lookup(data, 'ci.legs');
    return Array.isArray(legs) ? legs.length : undefined;
  }

  function valueAt(data, path) {
    if (Object.prototype.hasOwnProperty.call(DERIVED, path)) {
      return DERIVED[path](data);
    }
    return lookup(data, path);
  }

  // Only web, relative and fragment links. Browsers drop control characters and spaces inside a
  // URL before they read its scheme, so they are dropped here too.
  function isSafeUrl(url) {
    var compact = String(url).replace(/[\u0000- \u007f]/g, '');
    var scheme = /^([a-z][a-z0-9+.-]*):/i.exec(compact);
    return !scheme || /^https?$/i.test(scheme[1]);
  }

  function docsBase(data) {
    var docs = lookup(data, 'release.links.docs');
    if (isBlank(docs) || !isSafeUrl(docs)) {
      return null;
    }
    return /\/$/.test(docs) ? docs : docs + '/';
  }

  // The API page anchors modules, not symbols: `jnwb.laminar` is `#module-jnwblaminar`.
  function apiUrl(docs, module) {
    var anchor = module ? '#module-' + encodeURIComponent(String(module).replace(/\./g, '').toLowerCase()) : '';
    return docs + 'api/' + anchor;
  }

  function symbolModules(data) {
    var modules = Object.create(null);  // no prototype: a symbol named `constructor` stays unmapped
    var groups = lookup(data, 'api.groups');
    (Array.isArray(groups) ? groups : []).forEach(function (group) {
      (Array.isArray(group.symbols) ? group.symbols : []).forEach(function (symbol) {
        modules[String(symbol)] = group.module;
      });
    });
    return modules;
  }

  function column(rows, key) {
    return rows.map(function (row) {
      return isMissing(row[key]) ? null : row[key];
    });
  }

  function field(key) {
    return function (row) {
      return row[key];
    };
  }

  // ---- DOM helpers --------------------------------------------------------

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function emptyText(list) {
    return Array.isArray(list) ? NONE_RECORDED : NOT_RECORDED;
  }

  function emptyNote(text) {
    return make('p', 'empty', text || NOT_RECORDED);
  }

  function setEmpty(container) {
    container.textContent = '';
    container.appendChild(emptyNote());
  }

  function setText(node, value) {
    if (isMissing(value)) {
      node.textContent = NOT_RECORDED;
      node.classList.add('empty');
    } else {
      node.textContent = String(value);
      node.classList.remove('empty');
    }
  }

  function setHref(node, value) {
    if (isBlank(value) || !isSafeUrl(value)) {
      node.removeAttribute('href');
      node.classList.add('empty');
      node.title = NOT_RECORDED;
    } else {
      node.setAttribute('href', String(value));
      node.classList.remove('empty');
      node.removeAttribute('title');
    }
  }

  function option(value, text) {
    var node = make('option', '', text);
    node.value = value;
    return node;
  }

  function cellWith(value) {
    var cell = make('td');
    setText(cell, value);
    return cell;
  }

  function fillSlots(data) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-slot]'), function (node) {
      setText(node, valueAt(data, node.getAttribute('data-slot')));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-slot-href]'), function (node) {
      setHref(node, lookup(data, node.getAttribute('data-slot-href')));
    });
  }

  // ---- Markdown-lite ------------------------------------------------------

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Inline code, [label](url) links and **bold**. The text is escaped first, so nothing in the
  // record reaches the page as markup; the only tags are the ones written here.
  function markdownLite(text) {
    return String(text).split(/`([^`]+)`/).map(function (part, index) {
      if (index % 2 === 1) {
        return '<code>' + escapeHtml(part) + '</code>';
      }
      return formatPlain(escapeHtml(part));
    }).join('');
  }

  function formatPlain(escaped) {
    return escaped
      .replace(/\[([^\]]+)\]\(([^()\s]+)\)/g, function (whole, label, url) {
        if (!isSafeUrl(url)) {
          return label;
        }
        return '<a href="' + url + '" rel="noopener noreferrer">' + label + '</a>';
      })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }

  // ---- theme --------------------------------------------------------------

  function storedTheme() {
    try {
      var value = window.localStorage.getItem(THEME_KEY);
      return THEMES.indexOf(value) === -1 ? 'system' : value;
    } catch (err) {
      return 'system';
    }
  }

  function storeTheme(choice) {
    try {
      window.localStorage.setItem(THEME_KEY, choice);
    } catch (err) {
      // Storage refused: the choice still holds for this page view.
    }
  }

  function tokens() {
    var style = window.getComputedStyle(document.documentElement);
    var names = {
      text: '--text', muted: '--muted', border: '--border', accent: '--accent',
      ok: '--ok', warn: '--warn', bad: '--bad'
    };
    var out = {};
    Object.keys(names).forEach(function (key) {
      out[key] = style.getPropertyValue(names[key]).trim();
    });
    return out;
  }

  function applyTheme(choice) {
    theme = choice;
    document.documentElement.setAttribute('data-theme', choice);
    document.getElementById('theme-toggle').title = 'Theme: ' + choice;
    var effective = choice;
    if (choice === 'system') {
      effective = systemDark && systemDark.matches ? 'dark' : 'light';
    }
    figureImages.forEach(function (img) {
      img.setAttribute('src', effective === 'dark' ? img.dataset.dark : img.dataset.light);
    });
    paintCharts();
  }

  function setupTheme() {
    document.getElementById('theme-toggle').addEventListener('click', function () {
      var next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
      storeTheme(next);
      applyTheme(next);
    });
    if (systemDark) {
      var onSystemChange = function () {
        if (theme === 'system') {
          applyTheme('system');
        }
      };
      if (systemDark.addEventListener) {
        systemDark.addEventListener('change', onSystemChange);
      } else if (systemDark.addListener) {
        systemDark.addListener(onSystemChange);
      }
    }
  }

  // ---- tabs ---------------------------------------------------------------

  function hashName() {
    var raw = window.location.hash.replace(/^#/, '');
    try {
      return decodeURIComponent(raw);
    } catch (err) {
      return raw;
    }
  }

  // Shows one tab panel and returns the name shown; an unknown name shows the overview.
  function selectTab(name, moveFocus) {
    var names = tabs.map(function (tab) {
      return tab.getAttribute('aria-controls');
    });
    var shown = names.indexOf(name) === -1 ? 'overview' : name;
    tabs.forEach(function (tab) {
      var on = tab.getAttribute('aria-controls') === shown;
      tab.setAttribute('aria-selected', on ? 'true' : 'false');
      tab.tabIndex = on ? 0 : -1;
      if (on && moveFocus) {
        tab.focus();
      }
    });
    names.forEach(function (panelName) {
      var panel = document.getElementById(panelName);
      if (panel) {
        panel.hidden = panelName !== shown;
      }
    });
    drawChartsIn(document.getElementById(shown));
    return shown;
  }

  function activate(name, moveFocus) {
    var shown = selectTab(name, moveFocus);
    try {
      window.history.replaceState(null, '', '#' + shown);
    } catch (err) {
      // The tab has switched; only the URL hash is left unset.
    }
  }

  function onTabKeydown(event) {
    var index = tabs.indexOf(event.currentTarget);
    var last = tabs.length - 1;
    var target;
    if (event.key === 'ArrowRight') {
      target = index === last ? 0 : index + 1;
    } else if (event.key === 'ArrowLeft') {
      target = index === 0 ? last : index - 1;
    } else if (event.key === 'Home') {
      target = 0;
    } else if (event.key === 'End') {
      target = last;
    } else {
      return;
    }
    event.preventDefault();
    activate(tabs[target].getAttribute('aria-controls'), true);
  }

  function setupTabs() {
    tabs = Array.prototype.slice.call(document.querySelectorAll('nav.tabs [role="tab"]'));
    tabs.forEach(function (tab) {
      var name = tab.getAttribute('aria-controls');
      var panel = document.getElementById(name);
      tab.id = 'tab-' + name;
      if (panel) {
        panel.setAttribute('aria-labelledby', tab.id);
      }
      tab.addEventListener('click', function () {
        activate(name, false);
      });
      tab.addEventListener('keydown', onTabKeydown);
    });
  }

  function setupCards() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-target]'), function (card) {
      var target = card.getAttribute('data-target');
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.addEventListener('click', function () {
        activate(target, false);
      });
      card.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activate(target, false);
        }
      });
    });
  }

  // ---- sortable, filtered tables -----------------------------------------

  function setTableEmpty(table, text) {
    table.appendChild(make('caption', 'empty', text));
  }

  // `rows` null means the section is not recorded. `matches(row, query)` filters on the
  // lower-cased search text.
  function makeTable(table, search, columns, rows, matches) {
    var sortIndex = -1;
    var direction = 1;
    var query = '';

    function choose(index) {
      if (sortIndex === index) {
        direction = -direction;
      } else {
        sortIndex = index;
        direction = 1;
      }
      paint();
    }

    function paint() {
      table.textContent = '';
      if (isMissing(rows) || !rows.length) {
        setTableEmpty(table, emptyText(rows));
        return;
      }
      var shown = rows.filter(function (row) {
        return !query || matches(row, query);
      });
      if (sortIndex !== -1) {
        var sortOf = columns[sortIndex].sort;
        shown = shown.slice().sort(function (a, b) {
          var x = sortOf(a);
          var y = sortOf(b);
          if (isBlank(x) || isBlank(y)) {
            // Missing values sort last whichever way the column runs.
            return isBlank(x) === isBlank(y) ? 0 : (isBlank(x) ? 1 : -1);
          }
          if (typeof x === 'number' && typeof y === 'number') {
            return direction * (x - y);
          }
          return direction * String(x).localeCompare(String(y));
        });
      }

      var head = make('tr');
      columns.forEach(function (column, index) {
        var arrow = '';
        if (index === sortIndex) {
          arrow = direction > 0 ? ' ' + UP : ' ' + DOWN;
        }
        var th = make('th', column.numeric ? 'num' : '', column.label + arrow);
        th.tabIndex = 0;
        th.setAttribute('aria-sort', index !== sortIndex ? 'none' : (direction > 0 ? 'ascending' : 'descending'));
        th.addEventListener('click', function () {
          choose(index);
        });
        th.addEventListener('keydown', function (event) {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            choose(index);
          }
        });
        head.appendChild(th);
      });
      var thead = make('thead');
      thead.appendChild(head);
      table.appendChild(thead);

      var tbody = make('tbody');
      if (!shown.length) {
        var none = make('tr');
        var cell = make('td', 'empty', 'No matches.');
        cell.colSpan = columns.length;
        none.appendChild(cell);
        tbody.appendChild(none);
      }
      shown.forEach(function (row) {
        var tr = make('tr');
        columns.forEach(function (column) {
          var td = make('td', column.numeric ? 'num' : '');
          var content = column.cell(row);
          if (content instanceof Node) {
            td.appendChild(content);
          } else {
            setText(td, content);
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
    }

    search.addEventListener('input', function () {
      query = search.value.trim().toLowerCase();
      paint();
    });
    paint();
  }

  // ---- releases -----------------------------------------------------------

  function entriesOf(release) {
    return Array.isArray(release.entries) ? release.entries : [];
  }

  function releaseLabel(release) {
    return String(release.version) + (release.date ? ' ' + MIDDOT + ' ' + release.date : '');
  }

  function renderReleases(data) {
    var releases = Array.isArray(data.releases) ? data.releases : [];
    var select = document.getElementById('release-select');
    var kindSelect = document.getElementById('release-kind');
    var search = document.getElementById('release-search');
    var box = document.getElementById('release-entries');
    var kinds = [];

    releases.forEach(function (release) {
      entriesOf(release).forEach(function (entry) {
        if (kinds.indexOf(entry.kind) === -1) {
          kinds.push(entry.kind);
        }
      });
    });
    kinds.forEach(function (kind) {
      kindSelect.appendChild(option(kind, kind));
    });
    releases.forEach(function (release, index) {
      select.appendChild(option(String(index), releaseLabel(release)));
    });
    select.disabled = !releases.length;
    kindSelect.disabled = !kinds.length;
    search.disabled = !releases.length;

    function paint() {
      box.textContent = '';
      var release = releases[Number(select.value)];
      if (!release) {
        box.appendChild(emptyNote());
        return;
      }
      var all = entriesOf(release);
      var kind = kindSelect.value;
      var query = search.value.trim().toLowerCase();
      var shown = all.filter(function (entry) {
        return (!kind || entry.kind === kind) &&
          (!query || String(entry.text).toLowerCase().indexOf(query) !== -1);
      });

      box.appendChild(make('h3', '', releaseLabel(release)));
      box.appendChild(make('p', 'lede', shown.length + ' of ' + all.length + ' entries'));
      if (!shown.length) {
        box.appendChild(emptyNote('No matching entries.'));
        return;
      }
      var list = make('ul');
      shown.forEach(function (entry) {
        var item = make('li');
        item.appendChild(make('span', 'tag', entry.kind));
        item.appendChild(document.createTextNode(' '));
        var body = make('span');
        body.innerHTML = markdownLite(entry.text);
        item.appendChild(body);
        list.appendChild(item);
      });
      box.appendChild(list);
    }

    select.addEventListener('change', paint);
    kindSelect.addEventListener('change', paint);
    search.addEventListener('input', paint);
    paint();
  }

  function renderCi(data) {
    var table = document.getElementById('ci-table');
    var legs = lookup(data, 'ci.legs');
    table.textContent = '';
    if (!Array.isArray(legs)) {
      setTableEmpty(table, NOT_RECORDED);
      return;
    }
    var head = make('tr');
    ['Python', 'OS', 'Note'].forEach(function (label) {
      head.appendChild(make('th', '', label));
    });
    var thead = make('thead');
    thead.appendChild(head);
    table.appendChild(thead);
    var tbody = make('tbody');
    legs.forEach(function (leg) {
      var tr = make('tr');
      tr.appendChild(cellWith(leg.python));
      tr.appendChild(cellWith(leg.os));
      tr.appendChild(make('td', '', leg.note || ''));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
  }

  // ---- validation ---------------------------------------------------------

  function testNames(row) {
    return Array.isArray(row.tests) ? row.tests : [];
  }

  function testsCell(row, openState) {
    var names = testNames(row);
    var key = row.file + '::' + row.qualname;
    var details = make('details');
    details.open = !!openState[key];
    details.addEventListener('toggle', function () {
      openState[key] = details.open;
    });
    details.appendChild(make('summary', '', String(names.length)));
    var list = make('ul', 'mono');
    names.forEach(function (name) {
      list.appendChild(make('li', '', name));
    });
    details.appendChild(list);
    return details;
  }

  function renderVerified(data) {
    var functions = lookup(data, 'verified.functions');
    var openState = {};
    var columns = [
      { label: 'File', sort: field('file'), cell: field('file') },
      { label: 'Function', sort: field('qualname'), cell: field('qualname') },
      { label: 'Verified at', sort: field('verified_at'), cell: field('verified_at') },
      {
        label: 'Tests',
        numeric: true,
        sort: function (row) { return testNames(row).length; },
        cell: function (row) { return testsCell(row, openState); }
      }
    ];
    makeTable(
      document.getElementById('verified-table'),
      document.getElementById('verified-search'),
      columns,
      Array.isArray(functions) ? functions : null,
      function (row, query) {
        return (String(row.file) + ' ' + String(row.qualname)).toLowerCase().indexOf(query) !== -1;
      }
    );
  }

  function renderReferences(data) {
    var references = lookup(data, 'references');
    var box = document.getElementById('references');
    box.textContent = '';
    if (!Array.isArray(references) || !references.length) {
      box.appendChild(emptyNote(emptyText(references)));
      return;
    }
    var list = make('ul');
    references.forEach(function (reference) {
      var item = make('li');
      if (!isBlank(reference.url) && isSafeUrl(reference.url)) {
        var link = make('a', '', reference.text);
        link.setAttribute('href', String(reference.url));
        link.setAttribute('rel', 'noopener noreferrer');
        item.appendChild(link);
      } else {
        item.textContent = String(reference.text);
      }
      list.appendChild(item);
    });
    box.appendChild(list);
  }

  // ---- performance and computational order -------------------------------

  function renderOrder(data) {
    var rows = lookup(data, 'order');
    makeTable(
      document.getElementById('order-table'),
      document.getElementById('order-search'),
      [
        { label: 'Export', sort: field('export'), cell: field('export') },
        { label: 'Order', sort: field('order'), cell: field('order') },
        { label: 'Evidence', sort: field('evidence'), cell: field('evidence') }
      ],
      Array.isArray(rows) ? rows : null,
      function (row, query) {
        return String(row.export).toLowerCase().indexOf(query) !== -1;
      }
    );
  }

  // One distinct color per series (Tableau 10, then two more), readable on both themes; a reused
  // color would merge two series, so more series than colors draw grey and say so in the legend.
  var SERIES_COLORS = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc948',
    '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac', '#86bcb6', '#d37295'];

  function seriesColor(index) {
    return index < SERIES_COLORS.length ? SERIES_COLORS[index] : null;
  }

  function axisStyle(colors) {
    return {
      color: colors.muted,
      gridcolor: colors.border,
      zerolinecolor: colors.border,
      linecolor: colors.border,
      automargin: true
    };
  }

  function baseLayout(colors) {
    return {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: colors.text },
      margin: { l: 48, r: 16, t: 16, b: 48 },
      showlegend: false,
      legend: { font: { color: colors.text } },
      xaxis: axisStyle(colors),
      yaxis: axisStyle(colors)
    };
  }

  function axisTitle(text, colors) {
    return { text: text, font: { color: colors.muted } };
  }

  // Plotly sizes a chart drawn in a hidden tab at its 700 px default and does not re-measure it
  // when the tab opens, so a chart is drawn only while its panel is shown. A hidden chart is
  // marked undrawn and drawn when its tab opens; a theme change redraws the visible ones.
  function addChart(box, spec) {
    charts.push({ box: box, spec: spec, drawn: false });
  }

  function drawChart(chart, colors) {
    var drawing = chart.spec(colors);
    Plotly.react(chart.box, drawing.data, drawing.layout, { responsive: true });
    chart.drawn = true;
  }

  function paintCharts() {
    if (!charts.length) {
      return;
    }
    if (typeof Plotly === 'undefined') {
      charts.forEach(function (chart) {
        chart.box.textContent = '';
        chart.box.appendChild(emptyNote('Chart unavailable: Plotly did not load.'));
      });
      return;
    }
    var colors = tokens();
    charts.forEach(function (chart) {
      if (chart.box.offsetParent !== null) {
        drawChart(chart, colors);
      } else {
        chart.drawn = false;
      }
    });
  }

  function drawChartsIn(panel) {
    if (typeof Plotly === 'undefined' || !panel) {
      return;
    }
    var colors = null;
    charts.forEach(function (chart) {
      if (!chart.drawn && panel.contains(chart.box)) {
        colors = colors || tokens();
        drawChart(chart, colors);
      }
    });
  }

  function renderReleaseCounts(releases) {
    var box = document.getElementById('chart-release-counts');
    if (!releases.length) {
      setEmpty(box);
      return;
    }
    var oldestFirst = releases.slice().reverse();
    var kinds = [];
    oldestFirst.forEach(function (release) {
      Object.keys(release.counts || {}).forEach(function (kind) {
        if (kinds.indexOf(kind) === -1) {
          kinds.push(kind);
        }
      });
    });
    addChart(box, function (colors) {
      var layout = baseLayout(colors);
      layout.barmode = 'stack';
      layout.showlegend = true;
      layout.xaxis.type = 'category';
      layout.yaxis.title = axisTitle('entries', colors);
      return {
        data: kinds.map(function (kind, index) {
          return {
            type: 'bar',
            name: seriesColor(index) ? kind : kind + ' (no distinct color)',
            x: oldestFirst.map(function (release) { return release.version; }),
            y: oldestFirst.map(function (release) {
              var counts = release.counts || {};
              return isMissing(counts[kind]) ? null : counts[kind];
            }),
            marker: { color: seriesColor(index) || colors.muted },
            hovertemplate: '%{x}<br>' + kind + ': %{y}<extra></extra>'
          };
        }),
        layout: layout
      };
    });
  }

  function renderBaseline(rows) {
    var box = document.getElementById('chart-baseline');
    if (!Array.isArray(rows) || !rows.length) {
      setEmpty(box);
      return;
    }
    addChart(box, function (colors) {
      var layout = baseLayout(colors);
      layout.xaxis.title = axisTitle('time_ms (log scale)', colors);
      // The timings span four orders of magnitude; a linear axis hides all but the slowest.
      layout.xaxis.type = 'log';
      layout.yaxis.type = 'category';
      layout.yaxis.autorange = 'reversed';
      return {
        data: [{
          type: 'bar',
          orientation: 'h',
          name: 'time_ms',
          x: column(rows, 'time_ms'),
          y: column(rows, 'name'),
          customdata: column(rows, 'peak_mb'),
          marker: { color: colors.accent },
          hovertemplate: '%{y}<br>time_ms %{x}<br>peak_mb %{customdata}<extra></extra>'
        }],
        layout: layout
      };
    });
  }

  function renderPeakMemory(peak) {
    var box = document.getElementById('chart-peak-memory');
    var meta = document.getElementById('peak-memory-meta');
    if (isMissing(peak)) {
      setText(meta, undefined);
    } else {
      setText(meta, 'version ' + (isMissing(peak.jnwb_version) ? NOT_RECORDED : peak.jnwb_version) +
        ' ' + MIDDOT + ' commit ' + (isMissing(peak.commit) ? NOT_RECORDED : peak.commit) +
        ' ' + MIDDOT + ' python ' + (isMissing(peak.python) ? NOT_RECORDED : peak.python) +
        ' ' + MIDDOT + ' platform ' + (isMissing(peak.platform) ? NOT_RECORDED : peak.platform));
    }
    var operations = !isMissing(peak) && Array.isArray(peak.operations) ? peak.operations : [];
    if (!operations.length) {
      setEmpty(box);
      return;
    }
    addChart(box, function (colors) {
      var layout = baseLayout(colors);
      layout.barmode = 'group';
      layout.showlegend = true;
      layout.xaxis.type = 'category';
      if (!isMissing(peak.unit)) {
        layout.yaxis.title = axisTitle(String(peak.unit), colors);
      }
      return {
        data: [
          {
            type: 'bar',
            name: 'peak_mib',
            x: column(operations, 'name'),
            y: column(operations, 'peak_mib'),
            marker: { color: colors.accent },
            hovertemplate: '%{x}<br>peak_mib %{y}<extra></extra>'
          },
          {
            type: 'bar',
            name: 'added_mib',
            x: column(operations, 'name'),
            y: column(operations, 'added_mib'),
            customdata: column(operations, 'added_is'),
            marker: { color: colors.ok },
            hovertemplate: '%{x}<br>added_mib %{y}<br>%{customdata}<extra></extra>'
          }
        ],
        layout: layout
      };
    });
  }

  // Numeric leaves of any shape, labelled by their path.
  function flatten(value, path, out) {
    if (isMissing(value)) {
      return out;
    }
    if (typeof value === 'number') {
      out.push({ label: path || 'import', value: value });
    } else if (typeof value === 'object') {
      Object.keys(value).forEach(function (key) {
        flatten(value[key], path ? path + '.' + key : key, out);
      });
    }
    return out;
  }

  function renderImport(imports) {
    var box = document.getElementById('chart-import');
    var leaves = flatten(imports, '', []);
    if (!leaves.length) {
      if (isMissing(imports)) {
        setEmpty(box);
        return;
      }
      box.textContent = '';
      var pre = make('pre');
      pre.textContent = JSON.stringify(imports, null, 2);
      pre.style.whiteSpace = 'pre-wrap';
      pre.style.overflowWrap = 'anywhere';
      box.appendChild(pre);
      return;
    }
    addChart(box, function (colors) {
      var layout = baseLayout(colors);
      layout.yaxis.type = 'category';
      layout.yaxis.autorange = 'reversed';
      return {
        data: [{
          type: 'bar',
          orientation: 'h',
          x: column(leaves, 'value'),
          y: column(leaves, 'label'),
          marker: { color: colors.accent },
          hovertemplate: '%{y}<br>%{x}<extra></extra>'
        }],
        layout: layout
      };
    });
  }

  function renderPerformance(data) {
    renderBaseline(lookup(data, 'performance.baseline'));
    renderPeakMemory(lookup(data, 'performance.peak_memory'));
    renderImport(lookup(data, 'performance.import'));
  }

  // ---- API ----------------------------------------------------------------

  function renderApi(data) {
    var groups = lookup(data, 'api.groups');
    var box = document.getElementById('api-groups');
    var search = document.getElementById('api-search');
    var docs = docsBase(data);
    var built = [];

    box.textContent = '';
    if (!Array.isArray(groups) || !groups.length) {
      box.appendChild(emptyNote(emptyText(groups)));
      return;
    }
    groups.forEach(function (group) {
      var symbols = Array.isArray(group.symbols) ? group.symbols : [];
      var label = group.module + ' (' + symbols.length + ')';
      if (!isBlank(group.extra)) {
        label += ' ' + MIDDOT + ' extra ' + group.extra;
      }
      var details = make('details');
      details.appendChild(make('summary', '', label));
      var list = make('ul');
      var items = symbols.map(function (symbol) {
        var name = String(symbol);
        var item = make('li');
        if (docs) {
          var link = make('a', '', name);
          link.setAttribute('href', apiUrl(docs, group.module));
          item.appendChild(link);
        } else {
          item.textContent = name;
        }
        list.appendChild(item);
        return { item: item, name: name };
      });
      details.appendChild(list);
      box.appendChild(details);
      built.push({ details: details, items: items });
    });

    function filter() {
      var query = search.value.trim().toLowerCase();
      built.forEach(function (group) {
        var shown = 0;
        group.items.forEach(function (entry) {
          var match = !query || entry.name.toLowerCase().indexOf(query) !== -1;
          entry.item.hidden = !match;
          if (match) {
            shown += 1;
          }
        });
        group.details.hidden = shown === 0;
        if (query && shown > 0) {
          group.details.open = true;
        }
      });
    }

    search.addEventListener('input', filter);
    filter();
  }

  // ---- figures ------------------------------------------------------------

  function renderFigures(data) {
    var figures = lookup(data, 'figures');
    var box = document.getElementById('figure-gallery');
    box.textContent = '';
    figureImages = [];
    if (!Array.isArray(figures) || !figures.length) {
      box.appendChild(emptyNote(emptyText(figures)));
      return;
    }
    figures.forEach(function (figure) {
      var node = make('figure');
      var img = make('img');
      img.alt = String(figure.title);
      img.loading = 'lazy';
      img.dataset.light = figure.light;
      img.dataset.dark = figure.dark;
      node.appendChild(img);
      var caption = make('figcaption');
      if (!isBlank(figure.docs_page) && isSafeUrl(figure.docs_page)) {
        var link = make('a', '', String(figure.title));
        link.setAttribute('href', String(figure.docs_page));
        link.setAttribute('rel', 'noopener noreferrer');
        caption.appendChild(link);
      } else {
        caption.textContent = String(figure.title);
      }
      node.appendChild(caption);
      box.appendChild(node);
      figureImages.push(img);
    });
  }

  // ---- OpenScope GLO showcases --------------------------------------------

  // Each group holds one block per species, so mouse and macaque results are never mixed.
  var SHOWCASE_GROUPS = [
    { status: 'published', id: 'showcase-published' },
    { status: 'exploratory', id: 'showcase-exploratory' },
    { status: 'verified', id: 'showcase-verified' }
  ];
  var SHOWCASE_SPECIES = [
    { species: 'mouse', label: 'Mouse' },
    { species: 'macaque', label: 'Macaque' }
  ];
  var NO_SHOWCASES = 'No showcase records yet';

  // A value as text, or as a code span for digests and commits.
  function textInto(parent, value, asCode) {
    var node = make(asCode ? 'code' : 'span');
    setText(node, value);
    parent.appendChild(node);
  }

  // Text as a link when the URL is safe, as plain text otherwise.
  function linkOrText(parent, text, url) {
    if (isBlank(url) || !isSafeUrl(url)) {
      textInto(parent, text);
      return;
    }
    var link = make('a', '', String(text));
    link.setAttribute('href', String(url));
    link.setAttribute('rel', 'noopener noreferrer');
    parent.appendChild(link);
  }

  function showcaseRow(parent, label, value, asCode) {
    var row = make('p');
    row.appendChild(make('strong', '', label + ': '));
    textInto(row, value, asCode);
    parent.appendChild(row);
  }

  // A labelled list of record items; build(element, item) fills the element for each item.
  function showcaseList(parent, label, items, build) {
    var head = make('p');
    head.appendChild(make('strong', '', label + ':'));
    parent.appendChild(head);
    if (!Array.isArray(items) || !items.length) {
      parent.appendChild(emptyNote(emptyText(items)));
      return;
    }
    var list = make('ul');
    items.forEach(function (item) {
      var li = make('li');
      build(li, item);
      list.appendChild(li);
    });
    parent.appendChild(list);
  }

  function showcaseFigures(parent, figures) {
    if (!Array.isArray(figures) || !figures.length) {
      parent.appendChild(emptyNote(emptyText(figures)));
      return;
    }
    var gallery = make('div', 'gallery');
    figures.forEach(function (figure) {
      var node = make('figure');
      var img = make('img');
      img.alt = String(figure.caption);
      img.loading = 'lazy';
      img.dataset.light = figure.light;
      img.dataset.dark = figure.dark;
      node.appendChild(img);
      var caption = make('figcaption');
      var line = make('p');
      setText(line, figure.caption);
      caption.appendChild(line);
      showcaseRow(caption, 'Units', figure.units);
      showcaseRow(caption, 'Controls', figure.controls);
      showcaseRow(caption, 'Uncertainty', figure.uncertainty);
      node.appendChild(caption);
      gallery.appendChild(node);
      figureImages.push(img);
    });
    parent.appendChild(gallery);
  }

  // One row per independent replication of the work. The verdict and the other fields are shown
  // as recorded; a digest shows its first characters, with the full value in the cell's title.
  var REPLICATION_COLUMNS = ['Verdict', 'By', 'Date', 'Scope', 'Seed', 'Report sha256', 'Note'];
  var DIGEST_CHARS = 12;

  function showcaseReplications(parent, rows) {
    var head = make('p');
    head.appendChild(make('strong', '', 'Replications:'));
    parent.appendChild(head);
    if (!Array.isArray(rows) || !rows.length) {
      parent.appendChild(emptyNote(emptyText(rows)));
      return;
    }
    var table = make('table');
    var header = make('tr');
    REPLICATION_COLUMNS.forEach(function (label) {
      header.appendChild(make('th', '', label));
    });
    table.appendChild(header);
    rows.forEach(function (row) {
      var tr = make('tr');
      tr.appendChild(cellWith(row.verdict));
      tr.appendChild(cellWith(row.by));
      tr.appendChild(cellWith(row.date));
      tr.appendChild(cellWith(row.scope));
      tr.appendChild(cellWith(row.seed === null ? 'none' : row.seed));
      var digest = make('td');
      var prefix = isMissing(row.report_sha256) ? row.report_sha256
        : String(row.report_sha256).slice(0, DIGEST_CHARS);
      textInto(digest, prefix, true);
      if (!isMissing(row.report_sha256)) {
        digest.title = String(row.report_sha256);
      }
      tr.appendChild(digest);
      tr.appendChild(cellWith(row.note));
      table.appendChild(tr);
    });
    var wrap = make('div', 'table-wrap');
    wrap.appendChild(table);
    parent.appendChild(wrap);
  }

  function showcaseCard(entry, docs, modules) {
    var card = make('article', 'panel');
    var title = make('h5');
    setText(title, entry.title);
    card.appendChild(title);
    card.appendChild(make('span', 'tag', String(entry.id)));

    var origin = entry.origin || {};
    var originRow = make('p');
    originRow.appendChild(make('strong', '', 'Origin: '));
    textInto(originRow, origin.kind);
    originRow.appendChild(document.createTextNode(' by '));
    textInto(originRow, origin.author);
    originRow.appendChild(document.createTextNode(', issue '));
    textInto(originRow, origin.issue === null ? 'none' : origin.issue);
    card.appendChild(originRow);

    showcaseRow(card, 'Question', entry.question);
    showcaseRow(card, 'Relation to published work', entry.relation_to_published);
    showcaseRow(card, 'Result', entry.result);
    showcaseRow(card, 'Interpretation', entry.interpretation);
    showcaseList(card, 'Limitations', entry.limitations, function (li, text) {
      textInto(li, text);
    });
    showcaseFigures(card, entry.figures);

    var dandi = entry.dandi || {};
    showcaseRow(card, 'DANDI dataset', dandi.id);
    showcaseRow(card, 'DANDI version', dandi.version);
    showcaseList(card, 'DANDI assets', dandi.assets, function (li, asset) {
      textInto(li, asset.asset_id);
      li.appendChild(document.createTextNode(' sha256 '));
      textInto(li, asset.sha256, true);
    });

    var jnwb = entry.jnwb || {};
    showcaseRow(card, 'jnwb commit', jnwb.commit, true);
    showcaseList(card, 'jnwb functions', jnwb.functions, function (li, name) {
      var url = docs ? apiUrl(docs, modules[String(name)]) : null;
      linkOrText(li, name, url);
    });

    var code = entry.code || {};
    var codeRow = make('p');
    codeRow.appendChild(make('strong', '', 'Code: '));
    linkOrText(codeRow, code.location, code.location);
    codeRow.appendChild(document.createTextNode(' at commit '));
    textInto(codeRow, code.commit, true);
    card.appendChild(codeRow);

    showcaseList(card, 'Receipts', entry.receipts, function (li, receipt) {
      textInto(li, receipt.name);
      li.appendChild(document.createTextNode(' sha256 '));
      textInto(li, receipt.sha256, true);
    });
    showcaseReplications(card, entry.replications);
    showcaseList(card, 'Links', entry.links, function (li, link) {
      linkOrText(li, link.label, link.url);
    });
    return card;
  }

  function renderShowcases(data) {
    var record = lookup(data, 'showcases');
    var entries = record && Array.isArray(record.entries) ? record.entries : null;
    var status = document.getElementById('showcase-status');
    var docs = docsBase(data);
    var modules = symbolModules(data);
    status.hidden = entries !== null;
    status.textContent = entries === null ? NO_SHOWCASES : '';
    SHOWCASE_GROUPS.forEach(function (group) {
      var box = document.getElementById(group.id);
      box.textContent = '';
      if (entries === null) {
        return;
      }
      SHOWCASE_SPECIES.forEach(function (species) {
        var block = make('div');
        block.appendChild(make('h4', '', species.label));
        var rows = entries.filter(function (entry) {
          return entry.status === group.status && entry.species === species.species;
        });
        if (!rows.length) {
          block.appendChild(emptyNote(NONE_RECORDED));
        }
        rows.forEach(function (entry) {
          block.appendChild(showcaseCard(entry, docs, modules));
        });
        box.appendChild(block);
      });
    });
  }

  // ---- overview and page --------------------------------------------------

  function render(data) {
    charts = [];
    fillSlots(data);
    renderReleases(data);
    renderCi(data);
    renderVerified(data);
    renderReferences(data);
    renderPerformance(data);
    renderOrder(data);
    renderApi(data);
    renderFigures(data);
    renderShowcases(data);
    renderReleaseCounts(Array.isArray(data.releases) ? data.releases : []);
    applyTheme(theme);
  }

  function showError(message) {
    var main = document.querySelector('main');
    if (!main) {
      return;
    }
    var box = make('div', 'panel', 'Could not show the dashboard data. ' + message);
    box.setAttribute('role', 'alert');
    main.insertBefore(box, main.firstChild);
  }

  function init() {
    applyTheme(storedTheme());
    setupTheme();
    setupTabs();
    setupCards();
    selectTab(hashName(), false);
    window.addEventListener('hashchange', function () {
      selectTab(hashName(), false);
    });
    fetch(DATA_URL, { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('data.json returned HTTP ' + response.status + '.');
        }
        return response.json();
      })
      .then(render)
      .catch(function (err) {
        showError(err && err.message ? err.message : String(err));
      });
  }

  init();
})();
