(function(){
  const $ = id => document.getElementById(id);
  const qs = sel => document.querySelector(sel);
  const qsa = sel => Array.from(document.querySelectorAll(sel));

  function setPanel(panel, open){
    if(!panel) return;
    panel.classList.toggle("open", open);
    panel.setAttribute("aria-hidden", open ? "false" : "true");
  }

  function closeFloating(){
    setPanel($("notificationsPanel"), false);
    setPanel($("favoritesPanel"), false);
    const results = $("globalSearchResults");
    if(results) results.classList.remove("open");
  }

  function wirePanels(){
    const notif = $("notificationsPanel");
    const fav = $("favoritesPanel");
    setPanel(notif, false);
    setPanel(fav, false);

    const list = $("notificationsList");
    if(list && !list.textContent.trim()){
      list.textContent = "Aucune notification pour le moment.";
    }
    const favList = $("favoritesList");
    if(favList && !favList.textContent.trim()){
      favList.textContent = "Aucun favori enregistre.";
    }

    const notifToggle = $("notificationsToggle");
    if(notifToggle){
      notifToggle.addEventListener("click", e=>{
        e.stopPropagation();
        const open = !notif.classList.contains("open");
        setPanel(fav, false);
        setPanel(notif, open);
      });
    }

    const favToggle = $("favoritesToggle");
    if(favToggle){
      favToggle.addEventListener("click", e=>{
        e.stopPropagation();
        const open = !fav.classList.contains("open");
        setPanel(notif, false);
        setPanel(fav, open);
      });
    }

    qsa("[data-close-notif]").forEach(btn=>{
      btn.addEventListener("click", ()=>setPanel(notif, false));
    });
  }

  function wireTheme(){
    const btn = $("themeToggle");
    if(!btn) return;
    const saved = localStorage.getItem("pronofoot-theme");
    if(saved === "light"){
      document.body.classList.add("theme-light");
      btn.textContent = "☀";
    }
    btn.addEventListener("click", ()=>{
      const light = document.body.classList.toggle("theme-light");
      localStorage.setItem("pronofoot-theme", light ? "light" : "dark");
      btn.textContent = light ? "☀" : "🌙";
    });
  }

  function wireSidebar(){
    const sidebar = $("sidebar");
    const collapse = $("sbCollapse");
    if(!sidebar || !collapse) return;
    collapse.addEventListener("click", ()=>{
      const collapsed = sidebar.classList.toggle("collapsed");
      collapse.textContent = collapsed ? "▶" : "◀ Reduire";
      collapse.setAttribute("aria-label", collapsed ? "Agrandir le menu" : "Reduire le menu");
    });
  }

  function wireSearchHints(){
    const search = $("search");
    const results = $("globalSearchResults");
    if(!search || !results) return;

    function build(){
      const q = search.value.trim().toLowerCase();
      if(q.length < 2){
        results.classList.remove("open");
        results.innerHTML = "";
        return;
      }
      const matches = [];
      if(Array.isArray(window.__PRONOFOOT_MATCHES)){
        window.__PRONOFOOT_MATCHES.forEach(m=>{
          if(matches.length >= 6) return;
          const label = `${m.home || ""} - ${m.away || ""}`;
          if(label.toLowerCase().includes(q)){
            matches.push({label, meta:m.league || "Match", key:`${m.home}|${m.away}`});
          }
        });
      }
      if(!matches.length){
        results.innerHTML = '<div class="gs-result">Aucun raccourci trouve</div>';
        results.classList.add("open");
        return;
      }
      results.innerHTML = matches.map(item =>
        `<div class="gs-result" role="option" data-key="${item.key}">${item.label}<small>${item.meta}</small></div>`
      ).join("");
      results.classList.add("open");
    }

    search.addEventListener("input", build);
    search.addEventListener("focus", build);
    results.addEventListener("click", e=>{
      const row = e.target.closest(".gs-result[data-key]");
      if(!row) return;
      const [home, away] = row.dataset.key.split("|");
      search.value = home;
      results.classList.remove("open");
      const match = Array.isArray(window.__PRONOFOOT_MATCHES)
        ? window.__PRONOFOOT_MATCHES.find(m=>m.home === home && m.away === away)
        : null;
      if(match && typeof window.showDetail === "function"){
        window.showDetail(match);
      }
      search.dispatchEvent(new Event("input", {bubbles:true}));
    });
  }

  function wireNavigation(){
    const nav = $("navHistory");
    const back = $("navBack");
    const forward = $("navForward");
    if(!nav || !back || !forward) return;
    nav.classList.add("visible");
    back.disabled = history.length <= 1;
    forward.disabled = true;
    back.addEventListener("click", ()=>history.back());
    forward.addEventListener("click", ()=>history.forward());
  }

  document.addEventListener("click", e=>{
    if(e.target.closest(".notifications-panel,.favorites-panel,.global-search-wrap,.icon-btn")) return;
    closeFloating();
  });
  document.addEventListener("keydown", e=>{
    if(e.key === "Escape") closeFloating();
  });

  wirePanels();
  wireTheme();
  wireSidebar();
  wireSearchHints();
  wireNavigation();
})();
