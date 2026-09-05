// Marquee items (kept from earlier)
(function () {
  const items = ['Peer Review','DOI Registry','ORCID Verified','Open Access','Faculty Approved','Citation Export','Diamond OA','Turnitin < 15%'];
  const targets = ['Editorial Review','Internal Screening','Frontend Deployment','Metadata Collection','Central Audit','DOI Activation'];
  const all = items.concat(targets);
  const track = document.getElementById('marqueeTrack');
  if (!track) return;
  const dup = all.concat(all);
  track.innerHTML = dup.map(label => `<span class="mq-item">\u2605 ${label}</span>`).join('');
})();

// Prototype banner dismiss
(function () {
  const banner = document.getElementById('protoBanner');
  const closeBtn = document.getElementById('protoClose');
  if (!banner || !closeBtn) return;
  if (localStorage.getItem('case-proto-dismissed') === '1') {
    banner.style.display = 'none';
  }
  closeBtn.addEventListener('click', function () {
    banner.style.display = 'none';
    try { localStorage.setItem('case-proto-dismissed', '1'); } catch (_) {}
  });
})();

// Submission gate
(function () {
  const form = document.getElementById('caseGate');
  const submitLink = document.getElementById('gateSubmit');
  const hint = document.getElementById('gateHint');
  if (!form || !submitLink || !hint) return;
  const topics = ['gate1','gate2','gate3'];
  const formUrl = 'https://docs.google.com/forms/d/e/1FAIpQLSf-zk_C4ieAJhTAC7kjF-7hUzpEAgRaBuZ7eR_Vs-a41UbzbQ/viewform';
  function update() {
    const allChecked = topics.every(id => form.querySelector('#' + id).checked);
    if (allChecked) {
      submitLink.classList.remove('disabled');
      submitLink.setAttribute('href', formUrl);
      submitLink.setAttribute('aria-disabled', 'false');
      hint.textContent = 'All three checkpoints acknowledged. Open the submission form to continue.';
      hint.style.color = 'var(--primary)';
    } else {
      submitLink.classList.add('disabled');
      submitLink.setAttribute('href', '#');
      submitLink.setAttribute('aria-disabled', 'true');
      hint.textContent = 'Tick all three checkpoints to enable submission.';
      hint.style.color = '';
    }
  }
  topics.forEach(id => {
    const el = form.querySelector('#' + id);
    if (el) el.addEventListener('change', update);
  });
  submitLink.addEventListener('click', function (e) {
    if (submitLink.getAttribute('aria-disabled') === 'true') {
      e.preventDefault();
      hint.textContent = 'Please tick all three mandatory checkpoints above first.';
      hint.style.color = '#a13a2a';
    }
  });
  update();
})();

// Lightweight nav active
(function () {
  const nav = document.getElementById('mainNav');
  if (!nav) return;
  const links = nav.querySelectorAll('a[href^="#"]');
  links.forEach(l => l.addEventListener('click', () => {
    nav.classList.remove('open');
    document.body.classList.remove('nav-open');
  }));
})();
