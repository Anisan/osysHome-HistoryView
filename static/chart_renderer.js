(function (global) {
  "use strict";

  const CUSTOM_PREFIX = "custom:";
  const IMAGE_URL_RE = /^https?:\/\//i;
  const IMAGE_EXT_RE = /\.(jpg|jpeg|png|gif|webp|bmp|svg|avif)(\?.*)?$/i;
  const PLAIN_CHART_TYPES = new Set([
    "gauge",
    "solidgauge",
    "pie",
    "variablepie",
    "pyramid",
    "funnel",
    "item",
  ]);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;")
      .replaceAll("'", "&#39;");
  }

  function isSafeImageUrl(value) {
    const text = String(value ?? "").trim();
    if (!text || !IMAGE_URL_RE.test(text)) return false;
    return IMAGE_EXT_RE.test(text) || /\/image/i.test(text) || /snapshot/i.test(text);
  }

  function deepMerge(target, source) {
    if (!source || typeof source !== "object") return target;
    const out = Array.isArray(target) ? target.slice() : { ...(target || {}) };
    Object.keys(source).forEach((key) => {
      const srcVal = source[key];
      const tgtVal = out[key];
      if (srcVal && typeof srcVal === "object" && !Array.isArray(srcVal) && tgtVal && typeof tgtVal === "object" && !Array.isArray(tgtVal)) {
        out[key] = deepMerge(tgtVal, srcVal);
      } else {
        out[key] = srcVal;
      }
    });
    return out;
  }

  function parseChartSelection(value, customChartTypeId) {
    const raw = String(value || "").trim();
    const legacyCustom = String(customChartTypeId || "").trim() || null;
    if (raw.startsWith(CUSTOM_PREFIX)) {
      const customId = raw.slice(CUSTOM_PREFIX.length).trim() || null;
      return { chartType: "line", customId };
    }
    if (legacyCustom) {
      return { chartType: raw || "line", customId: legacyCustom };
    }
    return { chartType: raw || "line", customId: null };
  }

  function formatChartSelection(chartType, customChartTypeId) {
    const customId = String(customChartTypeId || "").trim();
    if (customId) return CUSTOM_PREFIX + customId;
    return String(chartType || "line").trim() || "line";
  }

  function resolveDefinition(chartTypes, customChartTypeId, builtinChartType) {
    if (customChartTypeId) {
      const found = (chartTypes || []).find((item) => String(item.id) === String(customChartTypeId));
      if (found) {
        return {
          source: "custom",
          id: found.id,
          name: found.name,
          engine: found.engine || "js",
          options: found.options || {},
          transform_js: found.transform_js || null,
          schema_version: found.schema_version || 1,
        };
      }
    }
    const builtin = String(builtinChartType || "line").toLowerCase() || "line";
    return {
      source: "builtin",
      id: null,
      name: builtin,
      engine: "builtin",
      preset: builtin,
      options: {},
      transform_js: null,
      chart_type: builtin,
    };
  }

  function resolveDefinitionFromSelection(chartTypes, selection, customChartTypeId) {
    const parsed = parseChartSelection(selection, customChartTypeId);
    return resolveDefinition(chartTypes, parsed.customId, parsed.chartType);
  }

  function isMediaDefinition(definition) {
    if (!definition) return false;
    if (definition.preset === "media") return true;
    return definition.engine === "builtin" && definition.chart_type === "media";
  }

  function isCustomRenderable(definition) {
    if (!definition) return false;
    if (definition.source === "custom") return true;
    return isMediaDefinition(definition);
  }

  function shouldUseCustomRenderer(definition) {
    if (!definition) return false;
    if (definition.engine === "js") return Boolean(definition.transform_js);
    if (definition.engine === "options_merge" && definition.options && Object.keys(definition.options).length) {
      return true;
    }
    return isMediaDefinition(definition);
  }

  function buildMediaEntries(entries) {
    return (entries || [])
      .filter((entry) => entry && entry.added)
      .map((entry) => {
        const ts = Date.parse(entry.added);
        if (!Number.isFinite(ts)) return null;
        const url = String(entry.value ?? entry.display_value ?? "").trim();
        return {
          x: ts,
          y: 1,
          custom: {
            url,
            safeUrl: isSafeImageUrl(url) ? url : "",
            transition: entry.transition || "",
            source: entry.source || "",
            display: entry.display_value ?? entry.value ?? "",
          },
        };
      })
      .filter(Boolean);
  }

  function buildMediaOptions(ctx) {
    const labels = ctx.labels || {};
    const payload = ctx.payload || {};
    const entries = payload.entries || [];
    const data = buildMediaEntries(entries);
    const theme = ctx.theme || {};
    const targetId = ctx.targetId;
    const compact = Boolean(ctx.compact);
    const chartHeight = ctx.chartHeight || 420;

    return {
      chart: { renderTo: targetId, height: compact ? 320 : chartHeight },
      title: { text: payload.property_label || payload.title || "" },
      xAxis: { type: "datetime", ordinal: false, ...(ctx.xAxisRange || {}) },
      yAxis: {
        min: 0,
        max: 2,
        tickPositions: [1],
        title: { text: labels.events || "Events" },
        labels: {
          formatter: function () {
            return this.value === 1 ? (labels.change || "Change") : "";
          },
        },
      },
      tooltip: {
        useHTML: true,
        formatter: function () {
          const custom = this.point.custom || {};
          const when = ctx.formatDate ? ctx.formatDate(this.x) : new Date(this.x).toLocaleString();
          const safeUrl = custom.safeUrl;
          const img = safeUrl
            ? `<div style="margin-top:6px;"><img src="${escapeHtml(safeUrl)}" alt="" style="max-width:220px;max-height:120px;border-radius:4px;" /></div>`
            : "";
          return `<b>${escapeHtml(when)}</b><br>${escapeHtml(labels.value || "Value")}: ${escapeHtml(custom.display || "-")}${img}<br>${escapeHtml(labels.source || "Source")}: ${escapeHtml(custom.source || "-")}`;
        },
      },
      plotOptions: { scatter: { marker: { radius: 5, symbol: "circle" } } },
      series: [{
        name: labels.mediaSeries || "Media",
        type: "scatter",
        color: theme.primary || "#4e79a7",
        data,
      }],
      navigator: { enabled: !compact, series: { color: theme.primary || "#4e79a7" } },
      rangeSelector: { enabled: !compact, inputEnabled: false },
      credits: { enabled: false },
      _mediaStrip: data,
    };
  }

  function renderMediaStrip(container, data, labels) {
    if (!container) return;
    container.innerHTML = "";
    const strip = document.createElement("div");
    strip.className = "history-media-strip d-flex flex-wrap gap-2 mt-2";
    const items = (data || []).slice(-24);
    if (!items.length) {
      container.classList.add("d-none");
      return;
    }
    container.classList.remove("d-none");
    items.forEach((point) => {
      const custom = point.custom || {};
      const wrap = document.createElement("a");
      wrap.className = "history-media-thumb";
      wrap.href = custom.safeUrl || "#";
      wrap.target = "_blank";
      wrap.rel = "noopener";
      wrap.title = custom.display || "";
      if (custom.safeUrl) {
        const img = document.createElement("img");
        img.src = custom.safeUrl;
        img.alt = custom.display || "";
        img.loading = "lazy";
        img.style.maxHeight = "72px";
        img.style.maxWidth = "120px";
        img.style.borderRadius = "4px";
        wrap.appendChild(img);
      } else {
        wrap.textContent = String(custom.display || "-").slice(0, 40);
      }
      strip.appendChild(wrap);
    });
    container.appendChild(strip);
  }

  function ensureRenderTarget(options, ctx) {
    if (!options || typeof options !== "object" || Array.isArray(options)) return options;
    if (!ctx || !ctx.targetId) return options;
    const chart = options.chart && typeof options.chart === "object" && !Array.isArray(options.chart)
      ? { ...options.chart }
      : {};
    if (!chart.renderTo) chart.renderTo = ctx.targetId;
    if (chart.height == null) {
      if (ctx.compact) chart.height = 320;
      else if (ctx.chartHeight) chart.height = ctx.chartHeight;
    }
    return { ...options, chart };
  }

  function prefersPlainChart(options) {
    const type = String(options?.chart?.type || "").toLowerCase();
    return PLAIN_CHART_TYPES.has(type);
  }

  function runTransformJs(definition, ctx) {
    const code = String(definition.transform_js || "").trim();
    if (!code) return null;
    const fnBody = `return (${code})(ctx);`;
    const runner = new Function("ctx", fnBody);
    const result = runner(ctx);
    return ensureRenderTarget(result, ctx);
  }

  function applyDefinition(baseOptions, definition, ctx) {
    if (!definition || definition.engine === "builtin") {
      if (isMediaDefinition(definition)) {
        return buildMediaOptions(ctx);
      }
      return baseOptions ? { ...baseOptions } : null;
    }

    if (definition.engine === "options_merge") {
      return deepMerge(baseOptions ? { ...baseOptions } : {}, definition.options || {});
    }

    if (definition.engine === "js" && definition.transform_js) {
      return runTransformJs(definition, { ...ctx, baseOptions: baseOptions || null });
    }

    return baseOptions ? { ...baseOptions } : null;
  }

  function pickBuilder(options, ctx, chartBuilder) {
    const Highcharts = global.Highcharts;
    if (prefersPlainChart(options)) return Highcharts.chart;
    if (chartBuilder) return chartBuilder;
    if (ctx.useStock === false) return Highcharts.chart;
    if (options && (options.navigator || options.rangeSelector) && !prefersPlainChart(options)) {
      return Highcharts.stockChart;
    }
    return ctx.useStock === false ? Highcharts.chart : Highcharts.stockChart;
  }

  function renderChart(definition, ctx, chartBuilder) {
    const Highcharts = global.Highcharts;
    if (!Highcharts) throw new Error("Highcharts is not loaded");

    let options = null;
    let error = null;

    try {
      if (isMediaDefinition(definition)) {
        options = buildMediaOptions(ctx);
      } else {
        options = applyDefinition(ctx.baseOptions || null, definition, ctx);
      }
      if (!options) {
        throw new Error("Chart options were not produced");
      }

      options = ensureRenderTarget(options, ctx);
      const builder = pickBuilder(options, ctx || {}, chartBuilder);
      const chart = builder(options);
      if (ctx.mediaStripId && options._mediaStrip) {
        renderMediaStrip(document.getElementById(ctx.mediaStripId), options._mediaStrip, ctx.labels || {});
      }
      return { chart, options, error: null, usedStock: builder === Highcharts.stockChart };
    } catch (exc) {
      error = exc;
      if (ctx.fallbackOptions) {
        const builder = pickBuilder(ctx.fallbackOptions, ctx || {}, chartBuilder);
        const chart = builder(ensureRenderTarget(ctx.fallbackOptions, ctx));
        return { chart, options: ctx.fallbackOptions, error, usedStock: builder === Highcharts.stockChart };
      }
      throw exc;
    }
  }

  global.HistoryViewChartRenderer = {
    CUSTOM_PREFIX,
    escapeHtml,
    isSafeImageUrl,
    deepMerge,
    parseChartSelection,
    formatChartSelection,
    resolveDefinition,
    resolveDefinitionFromSelection,
    isMediaDefinition,
    isCustomRenderable,
    shouldUseCustomRenderer,
    ensureRenderTarget,
    prefersPlainChart,
    buildMediaEntries,
    buildMediaOptions,
    renderMediaStrip,
    applyDefinition,
    runTransformJs,
    renderChart,
  };
})(typeof window !== "undefined" ? window : this);
