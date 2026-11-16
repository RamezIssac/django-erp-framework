/**
 * erp_framework — prepopulated inline grid ("sheet").
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
 *     enterAsTab: true,
 *     autosave:  {url: "/.../grid-autosave/", messages: {...}}   // optional
 *   }
 *
 * Keyboard (spreadsheet-like):
 *   Up/Down            same column, previous/next row (Ctrl: first/last row)
 *   Left/Right         previous/next cell (visual, RTL aware); inside a cell
 *                      after F2 / double-click they move the caret instead
 *   Enter / Shift+Enter next / previous cell (wraps to next/previous row)
 *   PageUp/PageDown    10 rows up/down
 *   Home/End           first/last cell of the row
 *   F2                 edit inside the cell (caret at end)
 *   Escape             revert the cell to its value when it got focus
 *
 * Autosave: when a cell is committed (change event: blur, Enter...), the row
 * is POSTed (htmx.ajax) to the autosave endpoint. Saves are queued one at a
 * time; the page "Save" button waits for the queue before submitting.
 *
 * Dispatches `erp:totals` on the inline group (detail: {totals, summaries})
 * after every recalculation, and `erp:saved` (detail: {row, response}) after
 * each successful autosave.
 */
(function () {
  "use strict";

  // ── Safe expression compiler: identifiers, numbers, + - * / ( ) ──────────
  var TOKEN = /\s*(?:([A-Za-z_]\w*)|(\d+(?:\.\d+)?)|([-+*/()]))/y;

  function compile(expr) {
    var parts = [];
    TOKEN.lastIndex = 0;
    while (TOKEN.lastIndex < expr.length) {
      var start = TOKEN.lastIndex;
      var m = TOKEN.exec(expr);
      if (!m) {
        if (/^\s*$/.test(expr.slice(start))) break;
        throw new Error("erp grid: invalid expression " + JSON.stringify(expr));
      }
      parts.push(m[1] ? "v[" + JSON.stringify(m[1]) + "]" : m[2] || m[3]);
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

  var NAME_RE = /-(\d+)-(\w+)$/;

  function fieldName(el) {
    var m = NAME_RE.exec(el.name || "");
    return m ? m[2] : null;
  }

  function fieldInput(row, name) {
    return row.querySelector('[name$="-' + name + '"]');
  }

  function isEditable(el) {
    if (!el || el.disabled || el.readOnly || el.type === "hidden") return false;
    if (el.getAttribute("tabindex") === "-1") return false;
    if (el.offsetParent === null) return false; // not visible
    return true;
  }

  function isCell(el) {
    return el && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA");
  }

  function hasCaret(el) {
    return el.tagName === "INPUT" && (el.type === "text" || el.type === "search" || el.type === "tel");
  }

  function selectAll(el) {
    try {
      el.select();
    } catch (e) {
      /* some input types don't support select() */
    }
  }

  // ── Grid ────────────────────────────────────────────────────────────────
  function Grid(group, config) {
    this.group = group;
    group.classList.add("erp-grid");
    this.config = config;
    this.prefix = group.id.replace(/-group$/, "");
    this.form = group.closest("form");
    this.rtl = getComputedStyle(group).direction === "rtl";
    this.decimals = config.decimals || {};
    this.computed = (config.computed || []).map(function (pair) {
      return { name: pair[0], evaluate: compile(pair[1]) };
    });
    this.computedNames = this.computed.map(function (c) {
      return c.name;
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
    this.rowList = Array.prototype.filter.call(group.querySelectorAll("tr.form-row"), function (tr) {
      return !/-empty$/.test(tr.id) && !tr.classList.contains("empty-form");
    });
    this.rowList.forEach(function (row, i) {
      row.__erpIndex = i;
    });
    this.editing = null;

    this.buildTotalsBar();
    this.bind();
    this.recalculateAll();
    if (config.autosave) this.setupAutosave(config.autosave);
  }

  Grid.prototype.rows = function () {
    return this.rowList;
  };

  Grid.prototype.rowValues = function (row) {
    var values = {};
    var inputs = row.querySelectorAll("input, select");
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      var name = fieldName(el);
      if (name) values[name] = el.type === "checkbox" ? (el.checked ? 1 : 0) : toNumber(el.value);
    }
    return values;
  };

  Grid.prototype.recalculateRow = function (row) {
    var values = this.rowValues(row);
    var self = this;
    this.computed.forEach(function (c) {
      var result = c.evaluate(values);
      values[c.name] = result;
      var input = fieldInput(row, c.name);
      if (input) input.value = format(result, self.decimals[c.name]);
    });
    return values;
  };

  // Totals are kept incrementally: each row's contribution is cached, so a
  // keystroke only re-reads its own row instead of the whole sheet.
  Grid.prototype.contribution = function (values) {
    return this.totals.map(function (t) {
      return t.evaluate ? t.evaluate(values) : values[t.name] || 0;
    });
  };

  Grid.prototype.recalculateAll = function () {
    var self = this;
    this.contribs = [];
    this.sums = this.totals.map(function () {
      return 0;
    });
    this.rowList.forEach(function (row, i) {
      var c = self.contribution(self.recalculateRow(row));
      self.contribs[i] = c;
      c.forEach(function (v, k) {
        self.sums[k] += v;
      });
    });
    this.renderTotals();
  };

  Grid.prototype.rowChanged = function (row) {
    var values = this.recalculateRow(row);
    var i = row.__erpIndex;
    if (i === undefined || !this.totals.length) {
      this.renderTotals();
      return;
    }
    var next = this.contribution(values);
    var prev = this.contribs[i] || [];
    for (var k = 0; k < next.length; k++) this.sums[k] += next[k] - (prev[k] || 0);
    this.contribs[i] = next;
    this.renderTotals();
  };

  Grid.prototype.renderTotals = function () {
    if (!this.totals.length && !this.summaries.length) return;
    var self = this;
    var sums = {};
    this.totals.forEach(function (t, k) {
      sums[t.name] = self.sums ? self.sums[k] : 0;
      var out = self.totalsOutputs[t.name];
      if (out) out.textContent = format(sums[t.name], self.decimals[t.name]);
    });
    var summaries = this.summaries.map(function (s, i) {
      var value = s.evaluate(sums);
      var out = self.summaryOutputs[i];
      if (out) out.textContent = format(value, 2);
      return { label: s.label, value: value };
    });
    this.group.dispatchEvent(
      new CustomEvent("erp:totals", { bubbles: true, detail: { totals: sums, summaries: summaries } })
    );
  };

  // Backwards compatible name.
  Grid.prototype.recalculateTotals = Grid.prototype.recalculateAll;

  Grid.prototype.buildTotalsBar = function () {
    var bar = document.createElement("div");
    bar.className = "erp-grid-totals";
    this.totalsOutputs = {};
    this.summaryOutputs = [];
    var self = this;

    function item(label) {
      var wrap = document.createElement("div");
      wrap.className = "erp-grid-total";
      var l = document.createElement("span");
      l.className = "erp-grid-total-label";
      l.textContent = label;
      var v = document.createElement("span");
      v.className = "erp-grid-total-value";
      v.textContent = "0";
      wrap.appendChild(l);
      wrap.appendChild(v);
      bar.appendChild(wrap);
      return v;
    }

    this.totals.forEach(function (t) {
      if (!t.hidden) {
        var out = item(t.label);
        out.setAttribute("data-total", t.name);
        self.totalsOutputs[t.name] = out;
      }
    });
    this.summaries.forEach(function (s, i) {
      var out = item(s.label);
      out.setAttribute("data-summary", String(i));
      self.summaryOutputs[i] = out;
    });
    if (!this.totals.length && !this.summaries.length && !this.config.autosave) bar.hidden = true;
    this.group.appendChild(bar);
    this.totalsBar = bar;
  };

  // ── Navigation ──────────────────────────────────────────────────────────
  Grid.prototype.rowCells = function (row) {
    return Array.prototype.filter.call(row.querySelectorAll("input, select, textarea"), isEditable);
  };

  Grid.prototype.focusCell = function (el) {
    if (!el) return false;
    el.focus();
    return true;
  };

  /** Same column, `delta` rows away (skipping rows where it isn't editable). */
  Grid.prototype.moveVertical = function (el, delta, toEdge) {
    var row = el.closest("tr.form-row");
    var name = fieldName(el);
    if (!row || !name) return;
    var rows = this.rowList;
    var i = row.__erpIndex;
    var target;
    if (toEdge) {
      var step = delta > 0 ? -1 : 1;
      for (var j = delta > 0 ? rows.length - 1 : 0; j !== i; j += step) {
        target = fieldInput(rows[j], name);
        if (isEditable(target)) return this.focusCell(target);
      }
      return;
    }
    var dir = delta > 0 ? 1 : -1;
    var j2 = Math.max(0, Math.min(rows.length - 1, i + delta));
    // Land on the requested row, or the nearest editable one before it.
    for (; j2 !== i; j2 -= dir) {
      target = fieldInput(rows[j2], name);
      if (isEditable(target)) return this.focusCell(target);
    }
  };

  /** Previous/next editable cell in DOM order; `wrap` continues on adjacent rows. */
  Grid.prototype.moveHorizontal = function (el, dir, wrap) {
    var row = el.closest("tr.form-row");
    if (!row) return;
    var cells = this.rowCells(row);
    var next = cells[cells.indexOf(el) + dir];
    if (next) return this.focusCell(next);
    if (!wrap) return;
    for (var i = row.__erpIndex + dir; i >= 0 && i < this.rowList.length; i += dir) {
      cells = this.rowCells(this.rowList[i]);
      if (cells.length) return this.focusCell(dir > 0 ? cells[0] : cells[cells.length - 1]);
    }
  };

  Grid.prototype.onKeydown = function (event) {
    var el = event.target;
    if (!isCell(el) || !el.closest("tr.form-row") || event.altKey || event.metaKey) return;
    var key = event.key;
    var editing = this.editing === el;
    var verticalOk = el.tagName !== "SELECT" && el.tagName !== "TEXTAREA";

    switch (key) {
      case "ArrowDown":
      case "ArrowUp":
        if (!verticalOk) return;
        event.preventDefault();
        this.moveVertical(el, key === "ArrowDown" ? 1 : -1, event.ctrlKey);
        return;
      case "PageDown":
      case "PageUp":
        if (!verticalOk) return;
        event.preventDefault();
        this.moveVertical(el, key === "PageDown" ? 10 : -10);
        return;
      case "ArrowLeft":
      case "ArrowRight":
        if (editing && hasCaret(el)) return; // caret moves inside the cell
        event.preventDefault();
        var forward = key === "ArrowRight" ? !this.rtl : this.rtl;
        this.moveHorizontal(el, forward ? 1 : -1, false);
        return;
      case "Home":
      case "End":
        if (editing || event.ctrlKey) return;
        var cells = this.rowCells(el.closest("tr.form-row"));
        if (!cells.length) return;
        event.preventDefault();
        this.focusCell(key === "Home" ? cells[0] : cells[cells.length - 1]);
        return;
      case "Enter":
        if (!this.config.enterAsTab || event.ctrlKey) return;
        if (el.type === "submit" || el.type === "button" || el.tagName === "TEXTAREA") return;
        event.preventDefault();
        this.moveHorizontal(el, event.shiftKey ? -1 : 1, true);
        return;
      case "F2":
        if (!hasCaret(el)) return;
        event.preventDefault();
        this.editing = el;
        var end = el.value.length;
        el.setSelectionRange(end, end);
        return;
      case "Escape":
        if (el.__erpOriginal === undefined || el.value === el.__erpOriginal) return;
        event.preventDefault();
        el.value = el.__erpOriginal;
        this.editing = null;
        this.rowChanged(el.closest("tr.form-row"));
        selectAll(el);
        return;
    }
  };

  Grid.prototype.bind = function () {
    var self = this;

    this.group.addEventListener("input", function (event) {
      var row = event.target.closest("tr.form-row");
      if (row) self.rowChanged(row);
    });
    this.group.addEventListener("change", function (event) {
      var row = event.target.closest("tr.form-row");
      if (!row) return;
      self.rowChanged(row);
      if (self.autosave) self.scheduleSave(row);
    });
    this.group.addEventListener("keydown", function (event) {
      self.onKeydown(event);
    });

    // Select the whole value on focus (so typing replaces it), and highlight
    // the active row. Keyboard focus selects right away; for a mouse click the
    // caret is placed after focus, so selection happens on mouseup instead.
    function selectable(el) {
      return hasCaret(el) || (el.tagName === "INPUT" && el.type === "number" && !el.readOnly);
    }
    var pointerDown = false;
    var clickFocused = null;
    var activeRow = null;
    this.group.addEventListener("mousedown", function () {
      pointerDown = true;
    });
    this.group.addEventListener("focusin", function (event) {
      var el = event.target;
      var row = el.closest("tr.form-row");
      if (activeRow && activeRow !== row) activeRow.classList.remove("erp-row-active");
      if (row) row.classList.add("erp-row-active");
      activeRow = row;
      if (self.editing !== el) self.editing = null;
      el.__erpOriginal = el.value;
      if (!selectable(el)) return;
      if (pointerDown) clickFocused = el;
      else selectAll(el);
    });
    this.group.addEventListener("dblclick", function (event) {
      if (isCell(event.target) && hasCaret(event.target)) self.editing = event.target;
    });
    document.addEventListener("mouseup", function (event) {
      pointerDown = false;
      var el = clickFocused;
      clickFocused = null;
      if (el && event.target === el && document.activeElement === el && self.editing !== el) {
        event.preventDefault();
        selectAll(el);
      }
    });
  };

  // ── Autosave ────────────────────────────────────────────────────────────
  Grid.prototype.setupAutosave = function (options) {
    var self = this;
    this.autosave = options;
    this.messages = options.messages || {};
    this.objectId = this.group.getAttribute("data-erp-object-id") || "";
    this.queue = Promise.resolve();
    this.pending = []; // rows waiting, in order
    this.inflight = 0;
    this.failed = new Set();

    var status = document.createElement("div");
    status.className = "erp-grid-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    this.totalsBar.insertBefore(status, this.totalsBar.firstChild);
    this.statusEl = status;

    if (this.form) {
      // "Save" waits for queued autosaves, then submits with the same button.
      this.form.addEventListener("submit", function (event) {
        if (!self.busy()) return;
        event.preventDefault();
        var submitter = event.submitter;
        self.flush().then(function () {
          if (submitter && self.form.requestSubmit) self.form.requestSubmit(submitter);
          else self.form.submit();
        });
      });
    }
    window.addEventListener("beforeunload", function (event) {
      if (self.busy() || self.failed.size) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  };

  Grid.prototype.busy = function () {
    return this.pending.length > 0 || this.inflight > 0;
  };

  Grid.prototype.flush = function () {
    var self = this;
    return this.queue.then(function () {
      return self.busy() ? self.flush() : null;
    });
  };

  Grid.prototype.setStatus = function () {
    var m = this.messages;
    var el = this.statusEl;
    el.classList.remove("is-saving", "is-error", "is-saved");
    if (this.busy()) {
      el.textContent = m.saving || "Saving…";
      el.classList.add("is-saving");
    } else if (this.failed.size) {
      el.textContent = (m.failed || "%(count)s rows not saved").replace("%(count)s", this.failed.size);
      el.classList.add("is-error");
    } else {
      el.textContent = m.saved || "All changes saved";
      el.classList.add("is-saved");
    }
  };

  Grid.prototype.scheduleSave = function (row) {
    if (this.pending.indexOf(row) !== -1) return; // payload is read at send time
    var self = this;
    this.pending.push(row);
    row.classList.add("erp-row-dirty");
    this.setStatus();
    this.queue = this.queue
      .then(function () {
        return self.saveRow(row);
      })
      .catch(function (e) {
        if (window.console) console.error("erp grid autosave", e);
      });
  };

  Grid.prototype.payload = function (row) {
    var data = { _prefix: this.prefix, _row: row.id, _object_id: this.objectId || "" };
    function add(el) {
      if (!el.name || el.disabled) return;
      var type = el.type;
      if (type === "submit" || type === "button" || type === "file" || type === "reset") return;
      if ((type === "checkbox" || type === "radio") && !el.checked) return;
      if (el.tagName === "SELECT" && el.multiple) {
        data[el.name] = Array.prototype.filter
          .call(el.options, function (o) {
            return o.selected;
          })
          .map(function (o) {
            return o.value;
          });
        return;
      }
      data[el.name] = type === "checkbox" && !el.value ? "on" : el.value;
    }
    row.querySelectorAll("input, select, textarea").forEach(add);
    if (!this.objectId && this.form) {
      // Not created yet: send the main (header) form so the server can create it.
      Array.prototype.forEach.call(this.form.elements, function (el) {
        if (el.name === "csrfmiddlewaretoken" || el.closest(".inline-group")) return;
        add(el);
      });
    }
    return data;
  };

  Grid.prototype.csrfToken = function () {
    var input = this.form && this.form.querySelector("[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var m = /(?:^|;\s*)csrftoken=([^;]+)/.exec(document.cookie);
    return m ? decodeURIComponent(m[1]) : "";
  };

  /** POST via htmx.ajax (fetch fallback). Resolves {status, data}. */
  Grid.prototype.post = function (values) {
    var url = this.autosave.url;
    var headers = { "X-CSRFToken": this.csrfToken() };
    if (window.htmx && window.htmx.ajax) {
      return new Promise(function (resolve) {
        var done = function (event) {
          var cfg = event.detail.requestConfig || {};
          var params = cfg.parameters;
          var sentRow = params && (typeof params.get === "function" ? params.get("_row") : params._row);
          if (cfg.path !== url || sentRow !== values._row) return;
          document.body.removeEventListener("htmx:afterRequest", done);
          var xhr = event.detail.xhr;
          var data = null;
          try {
            data = JSON.parse(xhr.responseText);
          } catch (e) {
            /* non-JSON error page */
          }
          resolve({ status: xhr.status, data: data });
        };
        document.body.addEventListener("htmx:afterRequest", done);
        // Source/target is <body>, which isn't inside the form, so htmx does
        // not add the whole form's values to the request.
        window.htmx
          .ajax("POST", url, { source: document.body, values: values, headers: headers, swap: "none" })
          .catch(function () {
            document.body.removeEventListener("htmx:afterRequest", done);
            resolve({ status: 0, data: null });
          });
      });
    }
    var body = new URLSearchParams();
    Object.keys(values).forEach(function (k) {
      [].concat(values[k]).forEach(function (v) {
        body.append(k, v);
      });
    });
    return fetch(url, { method: "POST", body: body, headers: headers, credentials: "same-origin" }).then(
      function (r) {
        return r
          .json()
          .catch(function () {
            return null;
          })
          .then(function (data) {
            return { status: r.status, data: data };
          });
      },
      function () {
        return { status: 0, data: null };
      }
    );
  };

  Grid.prototype.saveRow = function (row) {
    var self = this;
    var i = this.pending.indexOf(row);
    if (i !== -1) this.pending.splice(i, 1);
    this.inflight++;
    row.classList.remove("erp-row-dirty");
    row.classList.add("erp-row-saving");
    this.setStatus();
    return this.post(this.payload(row)).then(function (result) {
      self.inflight--;
      row.classList.remove("erp-row-saving");
      self.clearErrors(row);
      var data = result.data || {};
      if (result.status === 200 && data.ok) {
        self.failed.delete(row);
        if (!self.objectId || data.created) self.adopt(data);
        if (data.pk) self.markSaved(row, data.pk);
        self.applyValues(row, data.values || {});
        row.classList.add("erp-row-saved");
        setTimeout(function () {
          row.classList.remove("erp-row-saved");
        }, 1200);
        self.group.dispatchEvent(
          new CustomEvent("erp:saved", { bubbles: true, detail: { row: row, response: data } })
        );
      } else {
        self.failed.add(row);
        row.classList.add("erp-row-error");
        self.showErrors(row, data.errors || { __all__: [self.messages.error || "Could not save this row."] });
      }
      self.setStatus();
    });
  };

  /** First save on the add page created the document: continue on its change URL. */
  Grid.prototype.adopt = function (data) {
    if (!data.objectId) return;
    document.querySelectorAll(".erp-grid-group").forEach(function (g) {
      g.setAttribute("data-erp-object-id", data.objectId);
      if (g.__erpGrid && g.__erpGrid.autosave) g.__erpGrid.objectId = data.objectId;
    });
    if (data.changeUrl) {
      if (this.form) this.form.setAttribute("action", data.changeUrl);
      try {
        history.replaceState(history.state, "", data.changeUrl);
      } catch (e) {
        /* ignore */
      }
    }
    // Header lookup (HeaderLookupAdminMixin) must now exclude this document.
    document.querySelectorAll("[hx-vals]").forEach(function (el) {
      try {
        var vals = JSON.parse(el.getAttribute("hx-vals"));
        if ("_object_id" in vals) {
          vals._object_id = data.objectId;
          el.setAttribute("hx-vals", JSON.stringify(vals));
        }
      } catch (e) {
        /* not JSON */
      }
    });
  };

  /**
   * The row now exists in the database. Make it an "initial" form of the
   * formset (index < INITIAL_FORMS, with its id) so the page Save updates it
   * instead of inserting a duplicate: swap its index with the first extra form.
   */
  Grid.prototype.markSaved = function (row, pk) {
    var idInput = fieldInput(row, "id");
    if (!idInput || idInput.value === String(pk)) return;
    var prefix = this.prefix;
    // Some themes render the management form twice (layout + inline
    // template); Django reads the last one, so keep every copy in sync.
    var initialInputs = (this.form || document).querySelectorAll('[name="' + prefix + '-INITIAL_FORMS"]');
    var initialInput = initialInputs[0];
    var initial = initialInput ? parseInt(initialInput.value, 10) : NaN;
    var index = parseInt(row.id.slice(prefix.length + 1), 10);
    if (initialInput && !isNaN(initial) && index >= initial) {
      if (index !== initial) {
        var other = document.getElementById(prefix + "-" + initial);
        if (other) {
          this.renumber(row, index, "__swap__");
          this.renumber(other, initial, index);
          this.renumber(row, "__swap__", initial);
        }
      }
      initialInputs.forEach(function (input) {
        input.value = initial + 1;
      });
    }
    idInput = fieldInput(row, "id");
    idInput.value = pk;
    row.classList.add("has_original");
  };

  Grid.prototype.renumber = function (row, from, to) {
    var prefix = this.prefix;
    var oldPart = prefix + "-" + from + "-";
    var newPart = prefix + "-" + to + "-";
    row.id = prefix + "-" + to;
    row.querySelectorAll("[name], [id], label[for]").forEach(function (el) {
      if (el.name) el.name = el.name.replace(oldPart, newPart);
      if (el.id) el.id = el.id.replace(oldPart, newPart);
      if (el.htmlFor) el.htmlFor = el.htmlFor.replace(oldPart, newPart);
    });
  };

  /** Server-computed values for computed (display-only) cells. */
  Grid.prototype.applyValues = function (row, values) {
    var changed = false;
    this.computedNames.forEach(function (name) {
      if (!(name in values)) return;
      var input = fieldInput(row, name);
      if (input && document.activeElement !== input && input.value !== values[name]) {
        input.value = values[name];
        changed = true;
      }
    });
    if (changed) this.rowChanged(row);
  };

  Grid.prototype.clearErrors = function (row) {
    row.classList.remove("erp-row-error");
    row.removeAttribute("title");
    row.querySelectorAll(".is-invalid").forEach(function (el) {
      el.classList.remove("is-invalid");
      el.removeAttribute("title");
    });
  };

  Grid.prototype.showErrors = function (row, errors) {
    var general = [];
    Object.keys(errors).forEach(function (name) {
      var messages = [].concat(errors[name]).map(function (e) {
        return typeof e === "string" ? e : e.message;
      });
      var input = name === "__all__" ? null : fieldInput(row, name);
      if (input && input.type !== "hidden") {
        input.classList.add("is-invalid");
        input.title = messages.join(" ");
      } else {
        general = general.concat(messages);
      }
    });
    if (general.length) row.title = general.join(" ");
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

  window.erpPrepopulatedGrid = { init: init, compile: compile, Grid: Grid };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
