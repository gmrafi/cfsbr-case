// CFSBR C.A.S.E. — interactions (1:1 with the original CCPM portal behaviour)
(function () {
  "use strict";

  // Marquee items — same list as the original portal
  var items = [
    "Assignment Series",
    "Peer Review",
    "DOI Registry",
    "ORCID Verified",
    "Open Access",
    "Faculty Approved",
    "Citation Export",
    "Bi-Monthly Issue"
  ];
  var track = document.getElementById("marqueeTrack");
  if (track) {
    var html = "";
    // 4 loops, exactly like the original
    for (var r = 0; r < 4; r++) {
      items.forEach(function (label) {
        html += '<span class="mq-item">' + label + '<span class="mq-star">★</span></span>';
      });
    }
    track.innerHTML = html;
  }

  // Prototype banner dismiss
  var banner = document.getElementById("protoBanner");
  var close = document.getElementById("protoClose");
  if (banner && close) {
    try {
      if (localStorage.getItem("case-banner-dismissed") === "1") banner.remove();
    } catch (e) {}
    close.addEventListener("click", function () {
      banner.remove();
      try { localStorage.setItem("case-banner-dismissed", "1"); } catch (e) {}
    });
  }

  // Mobile nav toggle
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }
})();
