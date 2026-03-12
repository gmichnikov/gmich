/**
 * Travel Log — Entry edit page: enable Save button only when form has changes.
 * Photos are autosaved; Save applies only to name, address, notes, visited_date.
 */
(function () {
  const form = document.querySelector('.tlog-form');
  const saveBtn = document.getElementById('tlog-save-btn');
  if (!form || !saveBtn) return;

  const fields = ['tlog-edit-name', 'tlog-edit-address', 'tlog-edit-date', 'tlog-edit-notes'];
  const inputs = fields.map(id => document.getElementById(id)).filter(Boolean);

  function getValues() {
    return inputs.map(el => (el && el.value) || '');
  }

  const initial = getValues();

  function isDirty() {
    const current = getValues();
    return initial.some((v, i) => v !== current[i]);
  }

  function updateSaveBtn() {
    saveBtn.disabled = !isDirty();
  }

  inputs.forEach(el => {
    el.addEventListener('input', updateSaveBtn);
    el.addEventListener('change', updateSaveBtn);
  });
})();
