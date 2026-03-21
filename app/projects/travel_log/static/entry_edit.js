/**
 * Travel Log — Entry edit page: enable Save button only when form has changes.
 * Photos are autosaved; Save applies only to name, address, notes, visited_date, tags.
 */
(function () {
  const form = document.querySelector('.tlog-form');
  const saveBtn = document.getElementById('tlog-save-btn');
  if (!form || !saveBtn) return;

  const fields = ['tlog-edit-name', 'tlog-edit-address', 'tlog-edit-date', 'tlog-edit-notes'];
  const inputs = fields.map(id => document.getElementById(id)).filter(Boolean);
  const tagCheckboxes = form.querySelectorAll('input[name="tag_ids"]');

  function getValues() {
    return inputs.map(el => (el && el.value) || '');
  }

  function getTagState() {
    return Array.from(tagCheckboxes).map(cb => cb.checked).join(',');
  }

  const initialValues = getValues();
  const initialTags = getTagState();

  function isDirty() {
    const valuesChanged = getValues().some((v, i) => v !== initialValues[i]);
    const tagsChanged = getTagState() !== initialTags;
    return valuesChanged || tagsChanged;
  }

  function updateSaveBtn() {
    saveBtn.disabled = !isDirty();
  }

  inputs.forEach(el => {
    el.addEventListener('input', updateSaveBtn);
    el.addEventListener('change', updateSaveBtn);
  });
  tagCheckboxes.forEach(el => {
    el.addEventListener('change', updateSaveBtn);
  });
})();
