/* Declare Before You Run — landing page behaviour.
   Vanilla JS, no dependencies. Every feature here is an enhancement:
   the page is complete and readable with this file absent. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- reveal on scroll ----------
     Figures animate once, when they first come into view. With reduced motion
     the CSS already renders everything in its final state, so skip entirely. */

  var animated = document.querySelectorAll("figure, .reveal, .tierdemo");

  if (reduceMotion || !("IntersectionObserver" in window)) {
    Array.prototype.forEach.call(animated, function (el) {
      el.classList.add("is-in");
    });
  } else {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -8% 0px" }
    );
    Array.prototype.forEach.call(animated, function (el) {
      observer.observe(el);
    });
  }

  /* ---------- disclosure tier demo ---------- */

  var RANK = { public: 0, restricted: 1, sealed: 2 };

  var READER_TEXT = {
    public:
      "The open register. Anyone can see that a covered run exists, when its commitments were lodged, which safeguards were disabled and what kinds of event it reported. Withheld fields appear as a salted hash — visible as present, unreadable as content.",
    restricted:
      "The embedded evaluator or regulator reviews the RunIntent in the three days before the run starts, receives each ExceptionNotice as it is lodged, and reads the findings every RunCloseout produces.",
    sealed:
      "After an incident, an investigator can open sealed fields under court order or equivalent legal process. The RunIntent's investigator_scope_expansion field grants a standing right to widen the scope of the inquiry."
  };

  /* Stand-in for a salted hash: deterministic, and clearly not real content. */
  function fauxHash(value) {
    var h = 0x811c9dc5;
    for (var i = 0; i < value.length; i++) {
      h ^= value.charCodeAt(i);
      h = (h * 0x01000193) >>> 0;
    }
    var out = "";
    for (var k = 0; k < 4; k++) {
      out += ("0000000" + h.toString(16)).slice(-8);
      h = (h * 0x01000193 + 0x9e3779b9) >>> 0;
    }
    return "sha256:" + out.slice(0, 24) + "…";
  }

  var tierButtons = document.querySelectorAll(".tier-controls button");
  var filingRows = document.getElementById("filingRows");
  var tierReader = document.getElementById("tierReader");

  function applyTier(reader) {
    var readerRank = RANK[reader];

    Array.prototype.forEach.call(tierButtons, function (btn) {
      btn.setAttribute("aria-pressed", String(btn.dataset.tier === reader));
    });

    if (tierReader) tierReader.textContent = READER_TEXT[reader];

    if (!filingRows) return;
    Array.prototype.forEach.call(filingRows.querySelectorAll(".frow"), function (row) {
      var fieldRank = RANK[row.dataset.tier];
      var val = row.querySelector(".fval");
      var value = val.dataset.value;

      if (fieldRank <= readerRank) {
        val.textContent = value;
        val.className = "fval is-open";
      } else if (row.dataset.tier === "sealed") {
        val.textContent = "sealed — encrypted to the registry";
        val.className = "fval is-sealed";
      } else {
        val.textContent = fauxHash(value);
        val.className = "fval is-hashed";
      }
    });
  }

  if (tierButtons.length) {
    Array.prototype.forEach.call(tierButtons, function (btn) {
      btn.addEventListener("click", function () {
        applyTier(btn.dataset.tier);
      });
    });
    applyTier("public");
  }

  /* ---------- schema: filing tabs ---------- */

  var schemaTabs = document.querySelectorAll(".schema-tabs button");
  if (schemaTabs.length) {
    Array.prototype.forEach.call(schemaTabs, function (tab) {
      tab.addEventListener("click", function () {
        Array.prototype.forEach.call(schemaTabs, function (other) {
          var panel = document.getElementById(other.dataset.panel);
          var on = other === tab;
          other.setAttribute("aria-selected", String(on));
          if (panel) panel.hidden = !on;
        });
      });
    });
  }

  /* ---------- results table view ---------- */

  var tableToggle = document.getElementById("tableToggle");
  var resultsTable = document.getElementById("resultsTable");
  if (tableToggle && resultsTable) {
    tableToggle.addEventListener("click", function () {
      var open = tableToggle.getAttribute("aria-expanded") === "true";
      tableToggle.setAttribute("aria-expanded", String(!open));
      resultsTable.hidden = open;
      tableToggle.textContent = open ? "Show the numbers as a table" : "Hide the table";
    });
  }
})();
