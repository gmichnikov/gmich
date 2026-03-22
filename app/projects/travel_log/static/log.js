/**
 * Travel Log — Log Place page: GPS, Places API, place selection, creation form.
 * Matches log.html structure (tlog- prefixed IDs/classes).
 */
(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const apiBase = '/travel-log/api/places';
  const tagsSuggestUrl = '/travel-log/api/tags/suggest';

  let userLat = null;
  let userLng = null;
  let gpsFailed = false;

  /** Last places returned from API (nearby or search); client filter runs on this snapshot. */
  let lastPlacesSnapshot = [];
  /** True when the last API response had zero places (vs. filter hiding all). */
  let lastApiReturnedEmpty = true;

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

  function getClientFilterNeedle() {
    return ($('#tlog-results-filter-input')?.value || '').trim().toLowerCase();
  }

  function placeMatchesClientFilter(p, needle) {
    if (!needle) return true;
    const hay = ((p.name || '') + ' ' + (p.address || '')).toLowerCase();
    return hay.includes(needle);
  }

  function getFilteredPlaces() {
    const needle = getClientFilterNeedle();
    return lastPlacesSnapshot.filter((p) => placeMatchesClientFilter(p, needle));
  }

  function updateClientFilterWrapVisibility() {
    const wrap = $('#tlog-results-client-filter-wrap');
    if (wrap) wrap.style.display = lastPlacesSnapshot.length > 0 ? 'block' : 'none';
  }

  function renderPlacesList(places) {
    const ul = $('#tlog-places-list');
    if (!ul) return;
    ul.innerHTML = '';
    if (places.length === 0) {
      if (lastApiReturnedEmpty) {
        ul.innerHTML =
          '<li class="tlog-no-results">No places found. Try a different search or <button type="button" class="tlog-inline-add-manual" id="tlog-inline-add-manual">add manually</button>.</li>';
        const btn = $('#tlog-inline-add-manual');
        if (btn) btn.addEventListener('click', showManualForm);
        showFallback();
      } else {
        ul.innerHTML =
          '<li class="tlog-no-results tlog-no-filter-matches">No places match your filter. Clear or change the text above to see all results.</li>';
      }
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

  /** Call after every nearby/search API response. */
  function setPlacesFromApi(places) {
    lastPlacesSnapshot = Array.isArray(places) ? places.slice() : [];
    lastApiReturnedEmpty = lastPlacesSnapshot.length === 0;
    const filterInput = $('#tlog-results-filter-input');
    if (filterInput) filterInput.value = '';
    updateClientFilterWrapVisibility();
    renderPlacesList(getFilteredPlaces());
  }

  function applyClientFilterOnly() {
    renderPlacesList(getFilteredPlaces());
  }

  function hideFinder() {
    const toggle = $('.tlog-log-mode-toggle');
    const nearbyPanel = $('#tlog-panel-nearby');
    const searchPanel = $('#tlog-panel-search');
    const results = $('#tlog-results');
    const categories = $('#tlog-categories');
    if (toggle) toggle.style.display = 'none';
    if (nearbyPanel) nearbyPanel.style.display = 'none';
    if (searchPanel) searchPanel.style.display = 'none';
    if (results) results.style.display = 'none';
    if (categories) categories.style.display = 'none';
  }

  function showFinder() {
    const toggle = $('.tlog-log-mode-toggle');
    const nearbyPanel = $('#tlog-panel-nearby');
    const searchPanel = $('#tlog-panel-search');
    if (toggle) toggle.style.display = 'flex';
    if (nearbyPanel) nearbyPanel.style.display = '';
    if (searchPanel) searchPanel.style.display = '';
    switchMode('nearby');
  }

  function setPlaceDetailInputs(place) {
    const v = (x) => (x != null && x !== '' ? String(x) : '');
    const el = (id) => $(id);
    const set = (id, key) => {
      const node = el(id);
      if (node) node.value = v(place[key]);
    };
    set('#tlog-form-primary-type', 'primary_type');
    set('#tlog-form-primary-type-display', 'primary_type_display_name');
    set('#tlog-form-short-address', 'short_formatted_address');
    set('#tlog-form-addr-locality', 'addr_locality');
    set('#tlog-form-addr-admin-1', 'addr_admin_area_1');
    set('#tlog-form-addr-admin-2', 'addr_admin_area_2');
    set('#tlog-form-addr-admin-3', 'addr_admin_area_3');
    set('#tlog-form-addr-country', 'addr_country_code');

    const gt = $('#tlog-form-google-types');
    if (gt) {
      const arr = Array.isArray(place.types) ? place.types : [];
      gt.value = JSON.stringify(arr);
    }

    const aa3Wrap = $('#tlog-form-addr-admin-3-wrap');
    if (aa3Wrap) {
      const loc = (place.addr_locality || '').trim();
      const aa3 = (place.addr_admin_area_3 || '').trim();
      const dup = loc && aa3 && loc === aa3;
      aa3Wrap.style.display = dup ? 'none' : '';
    }
  }

  function clearPlaceDetailInputs() {
    [
      '#tlog-form-primary-type',
      '#tlog-form-primary-type-display',
      '#tlog-form-short-address',
      '#tlog-form-addr-locality',
      '#tlog-form-addr-admin-1',
      '#tlog-form-addr-admin-2',
      '#tlog-form-addr-admin-3',
      '#tlog-form-addr-country',
    ].forEach((id) => {
      const node = $(id);
      if (node) node.value = '';
    });
    const aa3Wrap = $('#tlog-form-addr-admin-3-wrap');
    if (aa3Wrap) aa3Wrap.style.display = '';
    const gt = $('#tlog-form-google-types');
    if (gt) gt.value = '';
    clearCreateTagCheckboxes();
  }

  function clearCreateTagCheckboxes() {
    const form = $('#tlog-create-form');
    if (!form) return;
    form.querySelectorAll('input[name="tag_ids"].tlog-tag-chip-cb').forEach((cb) => {
      cb.checked = false;
    });
  }

  async function applySuggestedTagsFromPlace(place) {
    const types = Array.isArray(place.types) ? place.types : [];
    const primaryType = place.primary_type != null && place.primary_type !== '' ? String(place.primary_type) : '';
    try {
      const r = await fetch(tagsSuggestUrl, {
        method: 'POST',
        headers: getCsrfHeaders(),
        body: JSON.stringify({ types, primary_type: primaryType || null }),
      });
      if (!r.ok) return;
      const data = await r.json();
      const ids = new Set((data.tag_ids || []).map((x) => parseInt(x, 10)));
      const form = $('#tlog-create-form');
      if (!form) return;
      form.querySelectorAll('input[name="tag_ids"].tlog-tag-chip-cb').forEach((cb) => {
        const id = parseInt(cb.value, 10);
        cb.checked = ids.has(id);
      });
    } catch (_) {
      /* keep current checkbox state */
    }
  }

  async function selectPlace(place) {
    const formWrap = $('#tlog-form-wrap');
    if (!formWrap) return;

    $('#tlog-form-name').value = place.name || '';
    $('#tlog-form-address').value = place.address || '';
    $('#tlog-form-place-id').value = place.place_id || '';
    $('#tlog-form-lat').value = place.lat != null ? String(place.lat) : '';
    $('#tlog-form-lng').value = place.lng != null ? String(place.lng) : '';
    setPlaceDetailInputs(place);
    await applySuggestedTagsFromPlace(place);
    const dateEl = $('#tlog-form-date');
    if (dateEl && !dateEl.value) dateEl.value = new Date().toISOString().slice(0, 10);

    hideFinder();
    formWrap.style.display = 'block';
  }

  function showManualForm() {
    const formWrap = $('#tlog-form-wrap');
    if (!formWrap) return;

    $('#tlog-form-name').value = '';
    $('#tlog-form-address').value = '';
    $('#tlog-form-place-id').value = '';
    $('#tlog-form-lat').value = '';
    $('#tlog-form-lng').value = '';
    clearPlaceDetailInputs();
    clearCreateTagCheckboxes();
    const dateEl = $('#tlog-form-date');
    if (dateEl) dateEl.value = new Date().toISOString().slice(0, 10);

    hideFinder();
    formWrap.style.display = 'block';
  }

    function goBackFromForm() {
    const formWrap = $('#tlog-form-wrap');
    if (!formWrap) return;
    formWrap.style.display = 'none';
    showFinder();
  }

  function hideResults() {
    if ($('#tlog-results')) $('#tlog-results').style.display = 'none';
    if ($('#tlog-categories')) $('#tlog-categories').style.display = 'none';
    lastPlacesSnapshot = [];
    lastApiReturnedEmpty = true;
    const filterInput = $('#tlog-results-filter-input');
    if (filterInput) filterInput.value = '';
    const wrap = $('#tlog-results-client-filter-wrap');
    if (wrap) wrap.style.display = 'none';
  }

  function switchMode(mode) {
    const nearbyBtn = $('#tlog-mode-nearby');
    const searchBtn = $('#tlog-mode-search');
    const nearbyPanel = $('#tlog-panel-nearby');
    const searchPanel = $('#tlog-panel-search');
    if (!nearbyBtn || !searchBtn || !nearbyPanel || !searchPanel) return;

    const isNearby = mode === 'nearby';
    nearbyBtn.classList.toggle('tlog-mode-btn-active', isNearby);
    nearbyBtn.setAttribute('aria-selected', isNearby);
    searchBtn.classList.toggle('tlog-mode-btn-active', !isNearby);
    searchBtn.setAttribute('aria-selected', !isNearby);
    nearbyPanel.classList.toggle('tlog-log-panel-visible', isNearby);
    nearbyPanel.setAttribute('aria-hidden', !isNearby);
    searchPanel.classList.toggle('tlog-log-panel-visible', !isNearby);
    searchPanel.setAttribute('aria-hidden', isNearby);
    hideResults();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const browseBtn = $('#tlog-browse-btn');
    const searchInput = $('#tlog-search-input');
    const results = $('#tlog-results');
    const categoryBtns = $$('.tlog-cat-btn');
    const fallbackBtn = $('#tlog-fallback-btn');
    const createForm = $('#tlog-create-form');
    const collectionSelect = $('#tlog-collection-id');
    const nearbyModeBtn = $('#tlog-mode-nearby');
    const searchModeBtn = $('#tlog-mode-search');

    if (nearbyModeBtn) nearbyModeBtn.addEventListener('click', () => switchMode('nearby'));
    if (searchModeBtn) searchModeBtn.addEventListener('click', () => switchMode('search'));

    if (browseBtn) {
      browseBtn.addEventListener('click', async () => {
        showStatus('Getting location…');
        const places = await fetchNearby();
        showStatus('');
        if (places.length === 0 && gpsFailed) {
          showStatus('Location not available. You can search by name (include location in your search, e.g. "coffee Tokyo" or "ramen Myeongdong Seoul") or add manually.', true);
          showFallback();
        }
        updateFilterLabel(null, false);
        setPlacesFromApi(places);
        if (results) {
          results.style.display = 'block';
          if (places.length > 3 && $('#tlog-categories')) $('#tlog-categories').style.display = 'flex';
        }
      });
    }

    async function runSearch() {
      const q = searchInput?.value?.trim();
      if (!q) {
        if (results) results.style.display = 'none';
        const fl = $('#tlog-filter-label');
        if (fl) fl.style.display = 'none';
        showStatus('Enter what you want to find, then tap Search.', false);
        return;
      }
      const useLocation = $('#tlog-search-nearby')?.checked ?? true;
      showStatus('Searching…');
      const places = await fetchSearch(q, useLocation);
      showStatus('');
      updateFilterLabel(null, true);
      setPlacesFromApi(places);
      if (results) {
        results.style.display = 'block';
        if (places.length > 3 && $('#tlog-categories')) $('#tlog-categories').style.display = 'flex';
      }
    }

    const searchBtn = $('#tlog-search-btn');
    if (searchBtn) searchBtn.addEventListener('click', runSearch);
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          runSearch();
        }
      });
    }

    categoryBtns.forEach((btn) => {
      btn.addEventListener('click', async () => {
        const cat = btn.dataset.cat || null;
        categoryBtns.forEach((b) => b.classList.toggle('tlog-cat-active', b === btn));
        updateFilterLabel(cat);
        showStatus('Searching…');
        const places = await fetchNearby(cat);
        showStatus('');
        setPlacesFromApi(places);
      });
    });

    const resultsFilterInput = $('#tlog-results-filter-input');
    if (resultsFilterInput) {
      resultsFilterInput.addEventListener('input', applyClientFilterOnly);
    }

    if (fallbackBtn) fallbackBtn.addEventListener('click', showManualForm);

    if (createForm) {
      createForm.querySelectorAll('.tlog-form-cancel').forEach((btn) => {
        btn.addEventListener('click', goBackFromForm);
      });
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
