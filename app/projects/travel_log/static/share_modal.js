/**
 * Travel Log — collection share modal (owner only). Loads members, invite by email, remove editors.
 */
(function () {
  const modal = document.getElementById('tlog-share-modal');
  const openBtn = document.getElementById('tlog-share-open-btn');
  if (!modal || !openBtn) return;

  const backdrop = document.getElementById('tlog-share-modal-backdrop');
  const emailsInput = document.getElementById('tlog-share-emails-input');
  const inviteBtn = document.getElementById('tlog-share-invite-btn');
  const statusEl = document.getElementById('tlog-share-invite-status');
  const peopleList = document.getElementById('tlog-share-people-list');

  const membersUrl = modal.getAttribute('data-members-url');
  const inviteUrl = modal.getAttribute('data-invite-url');
  const removeUrl = modal.getAttribute('data-remove-url');

  function showModal() {
    modal.classList.remove('tlog-modal-hidden');
    modal.removeAttribute('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('tlog-modal-open');
    loadMembers();
  }

  function hideModal() {
    modal.classList.add('tlog-modal-hidden');
    modal.setAttribute('hidden', 'hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('tlog-modal-open');
    if (statusEl) statusEl.textContent = '';
  }

  function jsonHeaders() {
    return { 'Content-Type': 'application/json' };
  }

  function renderPeople(data) {
    if (!peopleList) return;
    peopleList.innerHTML = '';
    const owner = data.owner;
    if (owner) {
      const li = document.createElement('li');
      li.className = 'tlog-share-person tlog-share-person-owner';
      li.innerHTML =
        '<span class="tlog-share-person-name">' +
        escapeHtml(owner.display_name || owner.email) +
        '</span> <span class="tlog-share-person-role">Owner</span>';
      peopleList.appendChild(li);
    }
    (data.editors || []).forEach(function (ed) {
      const li = document.createElement('li');
      li.className = 'tlog-share-person';
      const name = escapeHtml(ed.display_name || ed.email);
      const email = escapeHtml(ed.email);
      li.innerHTML =
        '<span class="tlog-share-person-name">' +
        name +
        '</span> <span class="tlog-share-person-meta">' +
        email +
        '</span> <button type="button" class="tlog-share-remove-btn" data-user-id="' +
        ed.user_id +
        '">Remove</button>';
      peopleList.appendChild(li);
    });

    peopleList.querySelectorAll('.tlog-share-remove-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const uid = btn.getAttribute('data-user-id');
        removeEditor(uid);
      });
    });
  }

  function escapeHtml(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  async function loadMembers() {
    try {
      const r = await fetch(membersUrl, { headers: { Accept: 'application/json' } });
      if (!r.ok) return;
      const data = await r.json();
      renderPeople(data);
    } catch (_) {}
  }

  async function removeEditor(userId) {
    if (!confirm('Remove this person as an editor? Their past entries stay in the collection.')) return;
    try {
      const r = await fetch(removeUrl, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ user_id: parseInt(userId, 10) }),
      });
      if (r.ok) loadMembers();
    } catch (_) {}
  }

  openBtn.addEventListener('click', showModal);
  if (backdrop) backdrop.addEventListener('click', hideModal);

  if (inviteBtn) {
    inviteBtn.addEventListener('click', async function () {
      const emails = emailsInput ? emailsInput.value : '';
      if (statusEl) statusEl.textContent = 'Saving…';
      try {
        const r = await fetch(inviteUrl, {
          method: 'POST',
          headers: jsonHeaders(),
          body: JSON.stringify({ emails: emails }),
        });
        const data = await r.json().catch(function () {
          return {};
        });
        if (!r.ok) {
          if (statusEl) statusEl.textContent = data.error || 'Something went wrong.';
          return;
        }
        const parts = [];
        if (data.added && data.added.length) parts.push('Added: ' + data.added.join(', '));
        if (data.already_access && data.already_access.length) {
          parts.push('Already had access: ' + data.already_access.join(', '));
        }
        if (data.skipped_owner && data.skipped_owner.length) {
          parts.push('Skipped (owner): ' + data.skipped_owner.join(', '));
        }
        if (statusEl) statusEl.textContent = parts.length ? parts.join(' · ') : 'Done.';
        loadMembers();
        if (emailsInput) emailsInput.value = '';
      } catch (e) {
        if (statusEl) statusEl.textContent = 'Network error.';
      }
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !modal.classList.contains('tlog-modal-hidden')) hideModal();
  });
})();
