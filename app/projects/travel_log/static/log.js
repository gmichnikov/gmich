/**
 * Travel Log — Log Place page: GPS, Places API, place selection, creation form.
 * Matches log.html structure (tlog- prefixed IDs/classes).
 */
(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const apiBase = '/travel-log/api/places';

  let userLat = null;
  let userLng = null;
  let gpsFailed = false;

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  function getCsrfHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (csrfToken) h['X-CSRFToken'] = csrfToken;
    return h;
  }

  function showStatus(msg, isError = false) {
    const el = $('#tlog-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'tlog-log-status ' + (isError ? 'tlog-log-status-error' : 'tlog-log-status-info');
    el.style.display = msg ? 'block' : 'none';
  }

  function updateLocationIndicator() {
    const el = $('#tlog-location-indicator');
    if (!el) return;
    if (userLat != null && userLng != null) {
      el.textContent = 'Location: ✓ ' + userLat.toFixed(2) + '°, ' + userLng.toFixed(2) + '°';
      el.className = 'tlog-location-indicator tlog-location-ready';
    } else if (gpsFailed) {
      el.textContent = 'Location: Not available';
      el.className = 'tlog-location-indicator tlog-location-failed';
    } else {
      el.textContent = 'Location: Getting…';
      el.className = 'tlog-location-indicator tlog-location-loading';
    }
    const nearbyCb = $('#tlog-search-nearby');
    if (nearbyCb) {
      if (userLat != null && userLng != null) {
        nearbyCb.disabled = false;
        nearbyCb.checked = true;
      } else if (gpsFailed) {
        nearbyCb.disabled = true;
        nearbyCb.checked = false;
      }
    }
  }

  function getGps() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        gpsFailed = true;
        updateLocationIndicator();
        resolve(null);
        return;
      }
      updateLocationIndicator();
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          userLat = pos.coords.latitude;
          userLng = pos.coords.longitude;
          gpsFailed = false;
          updateLocationIndicator();
          resolve({ lat: userLat, lng: userLng });
        },
        () => {
          gpsFailed = true;
          updateLocationIndicator();
          resolve(null);
        },
        { timeout: 10000, maximumAge: 60000 }
      );
    });
  }

  function showFallback() {
    const fallback = $('#tlog-fallback');
    if (fallback) fallback.style.display = 'block';
  }

  async function fetchNearby(category = null) {
    try {
      const coords = userLat != null && userLng != null ? { lat: userLat, lng: userLng } : await getGps();
      if (!coords) return [];
      const body = { lat: coords.lat, lng: coords.lng, radius: 200 };
      if (category) body.category = category;
      const r = await fetch(apiBase + '/nearby', { method: 'POST', headers: getCsrfHeaders(), body: JSON.stringify(body) });
      if (!r.ok) {
        let errMsg = 'Could not fetch nearby places.';
        try {
          const d = await r.json();
          if (d && d.error) errMsg = d.error;
        } catch (_) {}
        showStatus(errMsg, true);
        showFallback();
        return [];
      }
      const data = await r.json();
      return data.places || [];
    } catch (e) {
      showStatus('Network error. Add place manually.', true);
      showFallback();
      return [];
    }
  }

  async function fetchSearch(query, useLocation = true) {
    try {
      const body = { query };
      if (useLocation && userLat != null && userLng != null) {
        body.lat = userLat;
        body.lng = userLng;
      }
      const r = await fetch(apiBase + '/search', { method: 'POST', headers: getCsrfHeaders(), body: JSON.stringify(body) });
      if (!r.ok) {
        let errMsg = 'Search failed. Please try again.';
        try {
          const d = await r.json();
          if (d && d.error) errMsg = d.error;
        } catch (_) {}
        showStatus(errMsg, true);
        showFallback();
        return [];
      }
      const data = await r.json();
      return data.places || [];
    } catch (e) {
      showStatus('Network error. Add place manually.', true);
      showFallback();
      return [];
    }
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  const CATEGORY_LABELS = { food: 'Food & Drink', shopping: 'Shopping', attractions: 'Attractions', other: 'Other' };

  function updateFilterLabel(category, fromSearch = false) {
    const el = $('#tlog-filter-label');
    if (!el) return;
    if (category && CATEGORY_LABELS[category]) {
      el.textContent = 'Filter: ' + CATEGORY_LABELS[category];
    } else if (fromSearch) {
      el.textContent = 'Search results';
    } else {
      el.textContent = 'Nearby places';
    }
    el.style.display = 'block';
  }

  function renderPlaces(places) {
    const ul = $('#tlog-places-list');
    if (!ul) return;
    ul.innerHTML = '';
    if (places.length === 0) {
      ul.innerHTML = '<li class="tlog-no-results">No places found. Try a different search or <button type="button" class="tlog-inline-add-manual" id="tlog-inline-add-manual">add manually</button>.</li>';
      const btn = $('#tlog-inline-add-manual');
      if (btn) btn.addEventListener('click', showManualForm);
      showFallback();
      return;
    }
    places.forEach((p) => {
      const li = document.createElement('li');
      li.className = 'tlog-place-item';
      const dist = p.distance_m != null ? ` · ${p.distance_m}m` : '';
      li.innerHTML = `<span class="tlog-place-name">${escapeHtml(p.name || '')}</span><span class="tlog-place-addr">${escapeHtml(p.address || '')}</span><span class="tlog-place-meta">${dist}</span>`;
      li.addEventListener('click', () => selectPlace(p));
      ul.appendChild(li);
    });
  }

  function selectPlace(place) {
    const formWrap = $('#tlog-form-wrap');
    const browse = $('.tlog-log-browse');
    const search = $('.tlog-log-search');
    const results = $('#tlog-results');
    const categories = $('#tlog-categories');
    if (!formWrap || !browse) return;

    $('#tlog-form-name').value = place.name || '';
    $('#tlog-form-address').value = place.address || '';
    $('#tlog-form-place-id').value = place.place_id || '';
    $('#tlog-form-lat').value = place.lat != null ? String(place.lat) : '';
    $('#tlog-form-lng').value = place.lng != null ? String(place.lng) : '';
    const dateEl = $('#tlog-form-date');
    if (dateEl && !dateEl.value) dateEl.value = new Date().toISOString().slice(0, 10);

    browse.style.display = 'none';
    if (search) search.style.display = 'none';
    if (results) results.style.display = 'none';
    if (categories) categories.style.display = 'none';
    formWrap.style.display = 'block';
  }

  function showManualForm() {
    const formWrap = $('#tlog-form-wrap');
    const browse = $('.tlog-log-browse');
    const search = $('.tlog-log-search');
    const results = $('#tlog-results');
    const categories = $('#tlog-categories');
    if (!formWrap) return;

    $('#tlog-form-name').value = '';
    $('#tlog-form-address').value = '';
    $('#tlog-form-place-id').value = '';
    $('#tlog-form-lat').value = '';
    $('#tlog-form-lng').value = '';
    const dateEl = $('#tlog-form-date');
    if (dateEl) dateEl.value = new Date().toISOString().slice(0, 10);

    browse.style.display = 'none';
    if (search) search.style.display = 'none';
    if (results) results.style.display = 'none';
    if (categories) categories.style.display = 'none';
    formWrap.style.display = 'block';
  }

  function goBackFromForm() {
    const formWrap = $('#tlog-form-wrap');
    const browse = $('.tlog-log-browse');
    const search = $('.tlog-log-search');
    const results = $('#tlog-results');
    const categories = $('#tlog-categories');
    if (!formWrap || !browse) return;

    formWrap.style.display = 'none';
    browse.style.display = 'block';
    if (search) search.style.display = 'block';
    if (results) results.style.display = 'none';
    if (categories) categories.style.display = 'none';
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  document.addEventListener('DOMContentLoaded', () => {
    const browseBtn = $('#tlog-browse-btn');
    const searchInput = $('#tlog-search-input');
    const results = $('#tlog-results');
    const categoryBtns = $$('.tlog-cat-btn');
    const fallbackBtn = $('#tlog-fallback-btn');
    const formCancel = $('#tlog-form-cancel');
    const createForm = $('#tlog-create-form');
    const collectionSelect = $('#tlog-collection-id');

    if (browseBtn) {
      browseBtn.addEventListener('click', async () => {
        showStatus('Getting location…');
        const places = await fetchNearby();
        showStatus('');
        if (places.length === 0 && gpsFailed) {
          showStatus('Location not available. You can search by name (include location in your search, e.g. "coffee Tokyo" or "ramen Myeongdong Seoul") or add manually.', true);
          showFallback();
        }
        updateFilterLabel(null, true);
        renderPlaces(places);
        if (results) {
          results.style.display = 'block';
          if (places.length > 3 && $('#tlog-categories')) $('#tlog-categories').style.display = 'flex';
        }
      });
    }

    const doSearch = debounce(async () => {
      const q = searchInput?.value?.trim();
      if (!q) {
        if (results) results.style.display = 'none';
        const fl = $('#tlog-filter-label');
        if (fl) fl.style.display = 'none';
        return;
      }
      const useLocation = $('#tlog-search-nearby')?.checked ?? true;
      showStatus('Searching…');
      const places = await fetchSearch(q, useLocation);
      showStatus('');
      updateFilterLabel(null, true);
      renderPlaces(places);
      if (results) {
        results.style.display = 'block';
        if (places.length > 3 && $('#tlog-categories')) $('#tlog-categories').style.display = 'flex';
      }
    }, 400);

    if (searchInput) searchInput.addEventListener('input', doSearch);

    categoryBtns.forEach((btn) => {
      btn.addEventListener('click', async () => {
        const cat = btn.dataset.cat || null;
        categoryBtns.forEach((b) => b.classList.toggle('tlog-cat-active', b === btn));
        updateFilterLabel(cat);
        showStatus('Searching…');
        const places = await fetchNearby(cat);
        showStatus('');
        renderPlaces(places);
      });
    });

    if (fallbackBtn) fallbackBtn.addEventListener('click', showManualForm);
    if (formCancel) formCancel.addEventListener('click', goBackFromForm);

    if (createForm) {
      createForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const collId = collectionSelect?.value || $('#tlog-form-collection-id')?.value;
        $('#tlog-form-collection-id').value = collId;
        const formData = new FormData(createForm);
        const body = Object.fromEntries(formData.entries());
        if (body.place_id === '') delete body.place_id;
        if (body.lat === '') delete body.lat;
        if (body.lng === '') delete body.lng;
        showStatus('Saving…');
        const r = await fetch('/travel-log/entries/create', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken || '' },
          body: new URLSearchParams(body),
        });
        showStatus('');
        if (r.ok) {
          const data = await r.json();
          if (data.redirect) window.location.href = data.redirect;
        } else {
          showStatus('Failed to save. Please try again.', true);
        }
      });
    }

    updateLocationIndicator();
    getGps();
  });
})();
