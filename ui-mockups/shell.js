/*
 * Lucid mockup shell: sidebar, header and composer.
 *
 * Rendered from one place so all screens share identical chrome. Pages only
 * provide <div id="sidebar-mount">, <div id="header-mount">, their <main> and
 * <div id="composer-mount">, then call LucidShell.mount({ ... }).
 */
(function () {
  "use strict";

  var DEFAULT_GROUPS = [
    {
      label: "Today",
      items: [
        { id: "evt", title: "Event-Driven Architecture & Bus" },
        { id: "tokens", title: "Tailwind Design System Tokens" },
      ],
    },
    {
      label: "Yesterday",
      items: [{ id: "pg", title: "PostgreSQL Partitioning Setup" }],
    },
    {
      label: "Previous 7 days",
      items: [
        { id: "graphql", title: "REST to GraphQL Migration" },
        { id: "docker", title: "Docker Best Practices" },
        { id: "system", title: "System Design Interview Prep" },
      ],
    },
  ];

  function row(item, activeId) {
    var isActive = item.id === activeId;
    var linkClass =
      "flex flex-1 items-center gap-2 pl-2.5 py-1.5 min-w-0 rounded-md text-[13px] transition-colors " +
      (isActive
        ? "bg-surface-elevated border border-surface-border-subtle/80 text-text-primary font-medium shadow-xs"
        : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated/40");
    var marker = isActive
      ? '<span class="w-1.5 h-1.5 rounded-full bg-amber-accent shrink-0"></span>'
      : '<span class="material-symbols-outlined text-[15px] text-text-muted shrink-0">history</span>';

    return (
      '<div class="group flex items-center gap-1 pr-1 rounded-md">' +
      '<a href="#" class="' +
      linkClass +
      '"' +
      (isActive ? ' aria-current="page"' : "") +
      ">" +
      marker +
      '<span class="truncate">' +
      item.title +
      "</span></a>" +
      '<button type="button" aria-label="Delete conversation" class="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1 rounded text-text-muted hover:text-danger transition-opacity">' +
      '<span class="material-symbols-outlined text-[15px]">delete</span>' +
      "</button>" +
      "</div>"
    );
  }

  function groupsMarkup(groups, activeId) {
    if (!groups || groups.length === 0) {
      return "";
    }
    return groups
      .map(function (group) {
        return (
          '<div class="space-y-1">' +
          '<div class="px-2 py-1 text-[11px] font-medium text-text-muted">' +
          group.label +
          "</div>" +
          '<nav class="space-y-0.5">' +
          group.items
            .map(function (item) {
              return row(item, activeId);
            })
            .join("") +
          "</nav></div>"
        );
      })
      .join("");
  }

  function dashboardRow(activeId) {
    var isActive = activeId === "dashboard";
    return (
      '<a href="dashboard.html" class="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[13px] transition-colors ' +
      (isActive
        ? "bg-surface-elevated border border-surface-border-subtle/80 text-text-primary font-medium shadow-xs"
        : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated/40") +
      '"' +
      (isActive ? ' aria-current="page"' : "") +
      ">" +
      '<span class="material-symbols-outlined text-[16px] ' +
      (isActive ? "text-amber-accent" : "text-text-muted") +
      '">monitoring</span>' +
      "<span>Dashboard</span>" +
      "</a>"
    );
  }

  function sidebar(options, groups) {
    var extra = options.sidebarExtra || "";
    return (
      '<aside id="main-sidebar" class="fixed lg:static top-0 bottom-0 left-0 w-[260px] bg-surface-sidebar z-40 flex flex-col justify-between select-none border-r border-surface-border -translate-x-full lg:translate-x-0 transition-transform duration-300 ease-in-out shrink-0 h-full">' +
      '<div class="flex flex-col flex-1 min-h-0">' +
      '<div class="h-16 px-4 flex items-center justify-between">' +
      '<div class="flex items-center gap-2">' +
      '<div class="w-5 h-5 rounded-full border-2 border-amber-accent flex items-center justify-center relative">' +
      '<span class="w-1.5 h-1.5 rounded-full bg-amber-accent absolute -top-0.5 right-0.5"></span>' +
      "</div>" +
      '<span class="font-semibold text-[17px] tracking-tight text-text-primary">Lucid</span>' +
      '<span class="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-surface-elevated border border-surface-border ml-1">v0.1</span>' +
      "</div>" +
      '<button type="button" aria-label="Close sidebar" class="p-1 rounded text-text-muted hover:text-text-primary lg:hidden" onclick="toggleSidebar(false)">' +
      '<span class="material-symbols-outlined text-[20px]">close</span>' +
      "</button>" +
      "</div>" +
      '<div class="px-3 pb-2">' +
      '<button type="button" class="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-surface-elevated hover:bg-surface-hover border border-surface-border-subtle text-text-primary text-[13px] font-medium transition-all group">' +
      '<span class="flex items-center gap-2">' +
      '<span class="material-symbols-outlined text-[17px] text-text-secondary group-hover:text-text-primary">add</span>' +
      "New chat</span>" +
      '<kbd class="font-mono text-[10px] text-text-muted bg-surface-sidebar px-1.5 py-0.5 rounded border border-surface-border">Ctrl K</kbd>' +
      "</button>" +
      "</div>" +
      '<div class="px-3 pb-2">' +
      dashboardRow(options.activeId) +
      "</div>" +
      '<div class="px-4"><div class="h-px bg-surface-border"></div></div>' +
      '<div class="flex-1 overflow-y-auto px-2 space-y-4 pt-2">' +
      groupsMarkup(groups, options.activeId) +
      extra +
      "</div>" +
      "</div>" +
      '<div class="p-3 border-t border-surface-border flex items-center gap-2.5">' +
      '<div class="w-7 h-7 rounded-full bg-surface-hover text-text-primary text-[12px] font-medium flex items-center justify-center shrink-0">R</div>' +
      '<span class="text-[13px] font-medium text-text-primary truncate">Renan</span>' +
      "</div>" +
      "</aside>" +
      '<div id="sidebar-backdrop" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-40 lg:hidden opacity-0 pointer-events-none transition-opacity duration-300" onclick="toggleSidebar(false)"></div>'
    );
  }

  function header(options) {
    return (
      '<header class="h-14 border-b border-surface-border px-4 sm:px-6 flex items-center justify-between shrink-0 bg-surface-bg/90 backdrop-blur-md z-20">' +
      '<div class="flex items-center gap-2 min-w-0">' +
      '<button type="button" aria-label="Open sidebar" class="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated lg:hidden" onclick="toggleSidebar(true)">' +
      '<span class="material-symbols-outlined text-[20px]">menu</span>' +
      "</button>" +
      '<h1 class="text-[13px] sm:text-[14px] font-medium text-text-primary truncate">' +
      (options.title || "New chat") +
      "</h1>" +
      "</div>" +
      "</header>"
    );
  }

  function composer(options) {
    var streaming = Boolean(options && options.streaming);
    var textarea = streaming
      ? '<textarea rows="1" disabled placeholder="Lucid is responding..." class="w-full bg-transparent resize-none text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none min-h-[44px] max-h-[140px] leading-relaxed opacity-50 cursor-not-allowed"></textarea>'
      : '<textarea rows="1" placeholder="Ask anything..." class="w-full bg-transparent resize-none text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none min-h-[44px] max-h-[140px] leading-relaxed"></textarea>';
    var left = streaming
      ? '<span class="flex items-center gap-2 text-[11px] text-text-muted font-mono"><span class="w-1.5 h-1.5 rounded-full bg-amber-accent animate-pulse"></span>Generating response</span>'
      : '<span class="text-[11px] text-text-muted font-mono">Enter to send &middot; Shift + Enter for new line</span>';
    var right = streaming
      ? '<button type="button" aria-label="Stop generating" class="flex items-center gap-1.5 h-8 px-3 rounded-full border border-amber-border bg-amber-dim text-amber-accent text-[12px] font-medium hover:bg-amber-accent/20 transition-colors"><span class="material-symbols-outlined text-[16px]">stop</span>Stop</button>'
      : '<button type="button" aria-label="Send message" class="w-8 h-8 rounded-full bg-amber-accent hover:bg-amber-hover text-[#261705] flex items-center justify-center transition-transform active:scale-95 shadow-sm"><span class="material-symbols-outlined text-[18px] font-bold">arrow_forward</span></button>';

    return (
      '<div class="bg-surface-elevated rounded-2xl border border-surface-border-subtle p-3 shadow-2xl transition-all ' +
      (streaming ? "" : "focus-within:border-amber-border") +
      '">' +
      textarea +
      '<div class="flex items-center justify-between pt-1 gap-2">' +
      left +
      '<div class="flex items-center gap-3">' +
      right +
      "</div></div></div>"
    );
  }

  function mount(options) {
    var opts = options || {};
    var groups = opts.groups === undefined ? DEFAULT_GROUPS : opts.groups;

    var sidebarMount = document.getElementById("sidebar-mount");
    var headerMount = document.getElementById("header-mount");
    var composerMount = document.getElementById("composer-mount");

    if (sidebarMount) {
      sidebarMount.innerHTML = sidebar(opts, groups);
    }
    if (headerMount) {
      headerMount.innerHTML = header(opts);
    }
    if (composerMount) {
      composerMount.innerHTML = composer(opts);
    }
  }

  window.toggleSidebar = function (open) {
    var sidebarEl = document.getElementById("main-sidebar");
    var backdrop = document.getElementById("sidebar-backdrop");
    if (!sidebarEl || !backdrop) {
      return;
    }
    if (open) {
      sidebarEl.classList.remove("-translate-x-full");
      sidebarEl.classList.add("translate-x-0");
      backdrop.classList.remove("opacity-0", "pointer-events-none");
      backdrop.classList.add("opacity-100", "pointer-events-auto");
    } else {
      sidebarEl.classList.remove("translate-x-0");
      sidebarEl.classList.add("-translate-x-full");
      backdrop.classList.remove("opacity-100", "pointer-events-auto");
      backdrop.classList.add("opacity-0", "pointer-events-none");
    }
  };

  window.copyCode = function (button) {
    var block = button.closest("[data-code-block]");
    var code = block ? block.querySelector("pre") : null;
    if (!code) {
      return;
    }
    var label = button.querySelector(".copy-label");
    navigator.clipboard.writeText(code.innerText).then(function () {
      if (!label) {
        return;
      }
      label.textContent = "Copied";
      setTimeout(function () {
        label.textContent = "Copy";
      }, 1600);
    });
  };

  window.LucidShell = {
    mount: mount,
    groups: DEFAULT_GROUPS,
    composer: composer,
  };
})();
