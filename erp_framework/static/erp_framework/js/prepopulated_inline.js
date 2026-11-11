/**
 * erp_framework — prepopulated inline grid.
 *
 * Configured per inline by a <script type="application/json" id="<prefix>-erp-grid">
 * emitted by PrepopulatedInlineMixin (see erp_framework/admin/prepopulated.py):
 *
 *   {
 *     computed:  [["value", "quantity * unit_price"], ...],   // per row, in order
 *     totals:    [{name: "quantity", label: "Quantity"},
 *                 {name: "total_weight", label: null, expr: "quantity * unit_weight", hidden: true}],
 *     summaries: [{label: "Avg price", expr: "value / quantity"}],  // over totals
 *     decimals:  {value: 2, ...},
 *     enterAsTab: true
 *   }
 *
 * Dispatches `erp:totals` on the inline group (detail: {totals, summaries})
 * after every recalculation so pages can hook extra behaviour.
 */
(function () {
  "use strict";

  // ── Safe expression compiler: identifiers, numbers, + - * / ( ) ──────────
  var TOKEN = /\s*(?:([A-Za-z_]\w*)|(\d+(?:\.\d+)?)|([-+*/()]))/y;

  function compile(expr) {
    var parts = [];
    var names = [];
    TOKEN.lastIndex = 0;
    while (TOKEN.lastIndex < expr.length) {
      var start = TOKEN.lastIndex;
      var m = TOKEN.exec(expr);
      if (!m) {
        if (/^\s*$/.test(expr.slice(start))) break;
        throw new Error("erp grid: invalid expression " + JSON.stringify(expr));
      }
      if (m[1]) {
        if (names.indexOf(m[1]) === -1) names.push(m[1]);
        parts.push("v[" + JSON.stringify(m[1]) + "]");
      } else {
        parts.push(m[2] || m[3]);
      }
    }
    // Only validated tokens reach the Function body.
    var fn = new Function("v", "return (" + parts.join(" ") + ");");
    return function (values) {
      var result;
      try {
        result = fn(values);
      } catch (e) {
        result = 0;
      }
      return isFinite(result) ? result : 0;
    };
  }

  function toNumber(value) {
    if (value === null || value === undefined || value === "") return 0;
    var n = parseFloat(String(value).replace(/,/g, ""));
    return isNaN(n) ? 0 : n;
  }

  function format(value, decimals) {
    if (decimals === null || decimals === undefined) decimals = 2;
    return Number(value).toFixed(decimals);
  }

  function fieldInput(row, name) {
    return row.querySelector('[name$="-' + name + '"]');
  }

  function isEditable(el) {
    if (el.disabled || el.readOnly || el.type === "hidden") return false;
    if (el.getAttribute("tabindex") === "-1") return false;
    if (el.offsetParent === null) return false; // not visible
    return true;
  }

  // ── Grid ────────────────────────────────────────────────────────────────
  function Grid(group, config) {
    this.group = group;
    group.classList.add("erp-grid");
    this.config = config;
    this.decimals = config.decimals || {};
    this.computed = (config.computed || []).map(function (pair) {
      return { name: pair[0], evaluate: compile(pair[1]) };
    });
    this.summaries = (config.summaries || []).map(function (s) {
      return { label: s.label, evaluate: compile(s.expr) };
    });
    this.totals = (config.totals || []).map(function (t) {
      return {
        name: t.name,
        label: t.label,
        hidden: !!t.hidden,
        evaluate: t.expr ? compile(t.expr) : null,
      };
    });
    this.buildTotalsBar();
    this.bind();
    this.recalculateAll();
  }

  Grid.prototype.rows = function () {
    return Array.prototype.filter.call(
      this.group.querySelectorAll("tr.form-row"),
      function (tr) {
        return !/-empty$/.test(tr.id) && !tr.classList.contains("empty-form");
      }
    );
  };

  Grid.prototype.rowValues = function (row) {
    var values = {};
    row.querySelectorAll("input, select").forEach(function (el) {
      var match = /-\d+-(\w+)$/.exec(el.name || "");
      if (match) values[match[1]] = el.type === "checkbox" ? (el.checked ? 1 : 0) : toNumber(el.value);
    });
    return values;
  };

  Grid.prototype.recalculateRow = function (row) {
    if (!this.computed.length) return;
    var values = this.rowValues(row);
    var self = this;
    this.computed.forEach(function (c) {
      var result = c.evaluate(values);
      values[c.name] = result;
      var input = fieldInput(row, c.name);
      if (input) input.value = format(result, self.decimals[c.name]);
    });
  };

  Grid.prototype.recalculateTotals = function () {
    if (!this.totals.length && !this.summaries.length) return;
    var sums = {};
    var self = this;
    this.totals.forEach(function (t) {
      sums[t.name] = 0;
    });
    this.rows().forEach(function (row) {
      var values = self.rowValues(row);
      self.totals.forEach(function (t) {
        sums[t.name] += t.evaluate ? t.evaluate(values) : values[t.name] || 0;
      });
    });
    this.totals.forEach(function (t) {
      var out = self.totalsBar.querySelector('[data-total="' + t.name + '"]');
      if (out) out.textContent = format(sums[t.name], self.decimals[t.name]);
    });
    var summaries = this.summaries.map(function (s, i) {
      var value = s.evaluate(sums);
      var out = self.totalsBar.querySelector('[data-summary="' + i + '"]');
      if (out) out.textContent = format(value, 2);
      return { label: s.label, value: value };
    });
    this.group.dispatchEvent(
      new CustomEvent("erp:totals", { bubbles: true, detail: { totals: sums, summaries: summaries } })
    );
  };

  Grid.prototype.recalculateAll = function () {
    var self = this;
    this.rows().forEach(function (row) {
      self.recalculateRow(row);
    });
    this.recalculateTotals();
  };

  Grid.prototype.buildTotalsBar = function () {
    var bar = document.createElement("div");
    bar.className = "erp-grid-totals";
    if (!this.totals.length && !this.summaries.length) bar.hidden = true;

    function item(label, attr, key) {
      var wrap = document.createElement("div");
      wrap.className = "erp-grid-total";
      var l = document.createElement("span");
      l.className = "erp-grid-total-label";
      l.textContent = label;
      var v = document.createElement("span");
      v.className = "erp-grid-total-value";
      v.setAttribute(attr, key);
      v.textContent = "0";
      wrap.appendChild(l);
      wrap.appendChild(v);
      bar.appendChild(wrap);
    }

    this.totals.forEach(function (t) {
      if (!t.hidden) item(t.label, "data-total", t.name);
    });
    this.summaries.forEach(function (s, i) {
      item(s.label, "data-summary", String(i));
    });
    this.group.appendChild(bar);
    this.totalsBar = bar;
  };

  Grid.prototype.focusables = function () {
    return Array.prototype.filter.call(
      this.group.querySelectorAll("tr.form-row input, tr.form-row select, tr.form-row textarea"),
      isEditable
    );
  };

  Grid.prototype.bind = function () {
    var self = this;

    this.group.addEventListener("input", function (event) {
      var row = event.target.closest("tr.form-row");
      if (!row) return;
      self.recalculateRow(row);
      self.recalculateTotals();
    });
    this.group.addEventListener("change", function (event) {
      var row = event.target.closest("tr.form-row");
      if (!row) return;
      self.recalculateRow(row);
      self.recalculateTotals();
    });

    // Select the whole value on focus (so typing replaces it), and highlight
    // the active row. Keyboard focus selects right away; for a mouse click the
    // caret is placed after focus, so selection happens on mouseup instead.
    function selectAll(el) {
      try {
        el.select();
      } catch (e) {
        /* some input types don't support select() */
      }
    }
    function selectable(el) {
      return el.tagName === "INPUT" && (el.type === "number" || el.type === "text") && !el.readOnly;
    }
    var pointerDown = false;
    var clickFocused = null;
    this.group.addEventListener("mousedown", function () {
      pointerDown = true;
    });
    this.group.addEventListener("focusin", function (event) {
      var el = event.target;
      var row = el.closest("tr.form-row");
      self.group.querySelectorAll("tr.erp-row-active").forEach(function (r) {
        r.classList.remove("erp-row-active");
      });
      if (row) row.classList.add("erp-row-active");
      if (!selectable(el)) return;
      if (pointerDown) clickFocused = el;
      else selectAll(el);
    });
    document.addEventListener("mouseup", function (event) {
      pointerDown = false;
      var el = clickFocused;
      clickFocused = null;
      if (el && event.target === el && document.activeElement === el) {
        event.preventDefault();
        selectAll(el);
      }
    });

    if (this.config.enterAsTab) {
      this.group.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.metaKey) return;
        var el = event.target;
        if (el.tagName !== "INPUT" && el.tagName !== "SELECT") return;
        if (el.type === "submit" || el.type === "button") return;
        event.preventDefault();
        var list = self.focusables();
        var next = list[list.indexOf(el) + 1];
        if (next) next.focus();
      });
    }
  };

  function init() {
    document.querySelectorAll('script[type="application/json"][id$="-erp-grid"]').forEach(function (script) {
      var prefix = script.id.slice(0, -"-erp-grid".length);
      var group = document.getElementById(prefix + "-group");
      if (!group || group.__erpGrid) return;
      var config;
      try {
        config = JSON.parse(script.textContent);
      } catch (e) {
        return;
      }
      group.__erpGrid = new Grid(group, config);
    });
  }

  window.erpPrepopulatedGrid = { init: init, compile: compile };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
