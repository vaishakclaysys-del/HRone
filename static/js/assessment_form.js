document.addEventListener('DOMContentLoaded', init);

let rubricData = null;
let prefillData = {};

function getJsonFromScript(id) {
  const el = document.getElementById(id);
  if (!el) return null;

  try {
    return JSON.parse(el.textContent);
  } catch (error) {
    console.error(`Failed to parse ${id}`, error);
    return null;
  }
}

function getRootPath() {
  const rootPath = getJsonFromScript('rootPathData');
  if (typeof rootPath === 'string' && rootPath.trim()) {
    return rootPath.replace(/\/$/, '');
  }
  return '';
}

function buildRubricUrl(rubricName, rootPath) {
  const normalizedRoot = rootPath ? rootPath.replace(/\/$/, '') : '';
  return `${window.location.origin}${normalizedRoot}/static/rubrics/${encodeURIComponent(rubricName)}.json`;
}

function showFormError(message) {
  const formSections = document.getElementById('formSections');
  if (!formSections) return;

  formSections.innerHTML = '';
  const alert = document.createElement('div');
  alert.className = 'assessment-completed-banner';
  alert.innerHTML = `<div class="completed-title">Failed to load assessment form</div><div class="completed-message">${message}</div>`;
  formSections.appendChild(alert);
}

function escapeText(value) {
  return String(value ?? '');
}

function createLabel(text, required) {
  const label = document.createElement('div');
  label.className = 'question-text';

  const labelText = document.createElement('span');
  labelText.textContent = escapeText(text);
  label.appendChild(labelText);

  if (required) {
    const star = document.createElement('span');
    star.className = 'required-star';
    star.textContent = '*';
    label.appendChild(star);
  }

  return label;
}

function applyPrefill(input, fieldId) {
  const value = prefillData[fieldId];
  if (value === undefined || value === null || value === '') {
    return;
  }

  if (input.type === 'checkbox') {
    input.checked = Boolean(value);
    return;
  }

  if (input.type === 'radio') {
    input.checked = String(input.value) === String(value);
    return;
  }

  if (input.type === 'range') {
    input.value = value;
    return;
  }

  input.value = value;
}

function renderField(field) {
  const wrapper = document.createElement('div');
  const inputLikeFields = ['input', 'email', 'text', 'number', 'select', 'textarea', 'datetime-local'];
  wrapper.className = inputLikeFields.includes(field.type) ? 'input-row' : 'question-row';
  wrapper.id = `wrap_${field.id}`;
  wrapper.dataset.required = field.required ? 'true' : 'false';
  wrapper.dataset.fieldType = field.type;

  const label = createLabel(field.label, field.required);
  wrapper.appendChild(label);

  if (field.type === 'rating') {
    const group = document.createElement('div');
    group.className = 'rating-group';

    for (let value = 1; value <= (field.max || 5); value += 1) {
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = field.id;
      radio.value = value;
      radio.id = `${field.id}_${value}`;
      radio.dataset.scoreField = 'true';
      radio.dataset.scoreType = 'rating';
      radio.dataset.scoreMax = String(field.max || 5);
      applyPrefill(radio, field.id);
      group.appendChild(radio);

      const radioLabel = document.createElement('label');
      radioLabel.setAttribute('for', radio.id);
      radioLabel.textContent = value;
      group.appendChild(radioLabel);
    }

    wrapper.appendChild(group);
  } else if (field.type === 'rating_group') {
    const group = document.createElement('div');
    group.className = 'rating-group';
    group.style.flexWrap = 'wrap';
    group.style.justifyContent = 'flex-start';

    (field.subfields || []).forEach((subfield) => {
      const subRow = document.createElement('div');
      subRow.className = 'framework-row';
      subRow.id = `wrap_${subfield.id}`;
      subRow.dataset.required = field.required ? 'true' : 'false';
      subRow.dataset.fieldType = 'rating_group_subfield';

      const subLabel = createLabel(subfield.label, field.required);
      subRow.appendChild(subLabel);

      const subGroup = document.createElement('div');
      subGroup.className = 'rating-group';

      for (let value = 1; value <= (field.max || 5); value += 1) {
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = subfield.id;
        radio.value = value;
        radio.id = `${subfield.id}_${value}`;
        radio.dataset.scoreField = 'true';
        radio.dataset.scoreType = 'rating';
        radio.dataset.scoreMax = String(field.max || 5);
        applyPrefill(radio, subfield.id);
        subGroup.appendChild(radio);

        const radioLabel = document.createElement('label');
        radioLabel.setAttribute('for', radio.id);
        radioLabel.textContent = value;
        subGroup.appendChild(radioLabel);
      }

      subRow.appendChild(subGroup);

      if (field.required) {
        subRow.classList.add('required-field');
      }

      wrapper.appendChild(subRow);
    });
  } else if (field.type === 'slider') {
    const sliderWrap = document.createElement('div');
    sliderWrap.className = 'slider-wrap';

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.name = field.id;
    slider.min = field.min ?? 0;
    slider.max = field.max ?? 10;
    slider.step = field.step ?? 1;
    slider.value = field.min ?? 0;
    slider.dataset.scoreField = 'true';
    slider.dataset.scoreType = 'slider';
    slider.dataset.scoreMax = String(field.max ?? 10);
    applyPrefill(slider, field.id);
    sliderWrap.appendChild(slider);

    const sliderValue = document.createElement('div');
    sliderValue.className = 'slider-val';
    sliderValue.id = `${field.id}_value`;
    sliderValue.textContent = slider.value;
    sliderWrap.appendChild(sliderValue);

    if (field.labels && field.labels.length) {
      const labelsRow = document.createElement('div');
      labelsRow.className = 'slider-labels';
      field.labels.forEach((label) => {
        const labelItem = document.createElement('span');
        labelItem.textContent = label;
        labelsRow.appendChild(labelItem);
      });
      sliderWrap.appendChild(labelsRow);
    }

    slider.addEventListener('input', () => {
      sliderValue.textContent = slider.value;
      updateLiveScore();
    });

    wrapper.appendChild(sliderWrap);
  } else if (field.type === 'number') {
    const input = document.createElement('input');
    input.type = 'number';
    input.name = field.id;
    input.min = field.min ?? 0;
    input.max = field.max_input ?? 99;
    input.placeholder = field.placeholder || '';
    input.dataset.scoreField = 'true';
    input.dataset.scoreType = 'number';
    input.dataset.scoreCap = String(field.cap ?? 5);
    applyPrefill(input, field.id);
    wrapper.appendChild(input);
  } else if (field.type === 'select') {
    const select = document.createElement('select');
    select.name = field.id;
    (field.options || []).forEach((option) => {
      const optionEl = document.createElement('option');
      optionEl.value = option.value;
      optionEl.textContent = option.label;
      select.appendChild(optionEl);
    });
    applyPrefill(select, field.id);
    wrapper.appendChild(select);
  } else if (field.type === 'textarea') {
    const textarea = document.createElement('textarea');
    textarea.name = field.id;
    textarea.rows = field.rows || 3;
    textarea.placeholder = field.placeholder || '';
    applyPrefill(textarea, field.id);
    wrapper.appendChild(textarea);
  } else if (field.type === 'datetime-local') {
    const input = document.createElement('input');
    input.type = 'datetime-local';
    input.name = field.id;
    applyPrefill(input, field.id);
    wrapper.appendChild(input);
  } else {
    const input = document.createElement('input');
    input.type = field.type === 'email' ? 'email' : 'text';
    input.name = field.id;
    input.placeholder = field.placeholder || '';
    applyPrefill(input, field.id);
    wrapper.appendChild(input);
  }

  if (field.required) {
    wrapper.classList.add('required-field');
  }

  return wrapper;
}

function renderRecommendation(recommendation) {
  const wrapper = document.createElement('div');
  wrapper.className = 'recommend-group';
  wrapper.id = 'wrap_recommendation';

  const title = document.createElement('div');
  title.className = 'section-header';
  title.textContent = recommendation.label || 'Overall Recommendation';
  wrapper.appendChild(title);

  (recommendation.options || []).forEach((option) => {
    const optionRow = document.createElement('label');
    optionRow.className = 'recommend-option';

    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'recommendation';
    radio.value = option.value;

    const text = document.createElement('span');
    text.innerHTML = `<strong>${escapeText(option.label)}</strong><br>${escapeText(option.desc)}`;

    optionRow.appendChild(radio);
    optionRow.appendChild(text);
    wrapper.appendChild(optionRow);
  });

  return wrapper;
}

function renderRubric(rubric) {
  const formSections = document.getElementById('formSections');
  if (!formSections) return;

  formSections.innerHTML = '';
  setFormTitle(rubric.title || 'Assessment Form');

  (rubric.sections || []).forEach((section) => {
    const card = document.createElement('div');
    card.className = 'section-card';

    const header = document.createElement('div');
    header.className = 'section-header';
    header.textContent = section.title || section.id;
    card.appendChild(header);

    (section.fields || []).forEach((field) => {
      card.appendChild(renderField(field));
    });

    formSections.appendChild(card);
  });

  if (rubric.recommendation) {
    formSections.appendChild(renderRecommendation(rubric.recommendation));
  }

  updateLiveScore();
}
function setFormTitle(title) {
  const titleEl = document.getElementById('formTitle');
  if (titleEl) {
    titleEl.textContent = title || 'Loading assessment…';
  }
}

function computeRubricMaxTotal() {
  if (!rubricData || !Array.isArray(rubricData.sections)) {
    return 185;
  }

  let maxTotal = 0;

  rubricData.sections.forEach((section) => {
    (section.fields || []).forEach((field) => {
      if (!field.scored) {
        return;
      }

      if (field.type === 'rating') {
        maxTotal += parseInt(field.max || 5, 10);
        return;
      }

      if (field.type === 'rating_group') {
        const subCount = Array.isArray(field.subfields) ? field.subfields.length : 0;
        maxTotal += subCount * parseInt(field.max || 5, 10);
        return;
      }

      if (field.type === 'slider') {
        maxTotal += parseInt(field.max || 10, 10);
        return;
      }

      if (field.type === 'number') {
        maxTotal += parseInt(field.cap || field.max_input || 0, 10);
        return;
      }

      maxTotal += parseInt(field.max || 0, 10);
    });
  });

  return maxTotal || 185;
}

function updateLiveScore() {
  const scoreEl = document.getElementById('live-score');
  if (!scoreEl) return;

  let total = 0;

  document.querySelectorAll('[data-score-field="true"]').forEach((element) => {
    const type = element.dataset.scoreType || 'rating';
    const maxValue = parseInt(element.dataset.scoreMax || '5', 10);
    const cap = parseInt(element.dataset.scoreCap || '5', 10);

    if (type === 'slider') {
      total += Math.min(parseInt(element.value || 0, 10), maxValue);
      return;
    }

    if (type === 'number') {
      total += Math.min(parseInt(element.value || 0, 10), cap);
      return;
    }

    if (element.type === 'radio' && element.checked) {
      total += parseInt(element.value || 0, 10);
      return;
    }

    if (element.type === 'range') {
      total += Math.min(parseInt(element.value || 0, 10), maxValue);
    }
  });

  const maxTotal = computeRubricMaxTotal();
  const scoreValue = total === 0 ? '–' : Math.round((total / maxTotal) * 100);
  scoreEl.textContent = scoreValue;
  const hiddenScore = document.getElementById('final_score');
  if (hiddenScore) {
    hiddenScore.value = scoreValue === '–' ? '0' : String(scoreValue);
  }
}

function clearFieldErrors() {
  document.querySelectorAll('.field-error').forEach((element) => element.classList.remove('field-error'));
}

function validateForm() {
  clearFieldErrors();
  let hasError = false;

  document.querySelectorAll('.required-field').forEach((wrapper) => {
    const type = wrapper.dataset.fieldType;
    const required = wrapper.dataset.required === 'true';

    if (!required) return;

    if (type === 'rating') {
      const checked = wrapper.querySelector('input[type="radio"]:checked');
      if (!checked) {
        hasError = true;
        wrapper.classList.add('field-error');
      }
      return;
    }

    if (type === 'rating_group_subfield') {
      const checked = wrapper.querySelector('input[type="radio"]:checked');
      if (!checked) {
        hasError = true;
        wrapper.classList.add('field-error');
      }
      return;
    }

    const input = wrapper.querySelector('input, select, textarea');
    if (!input || !String(input.value).trim()) {
      hasError = true;
      wrapper.classList.add('field-error');
    }
  });

  const recommendation = document.querySelector('input[name="recommendation"]:checked');
  const recommendationWrap = document.getElementById('wrap_recommendation');
  if (!recommendation && recommendationWrap) {
    hasError = true;
    recommendationWrap.classList.add('field-error');
  }

  if (hasError) {
    const firstError = document.querySelector('.field-error');
    if (firstError) {
      firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  return !hasError;
}

async function init() {
  const rubricName = getJsonFromScript('rubricNameData');
  prefillData = getJsonFromScript('prefillData') || {};

  const assessmentForm = document.getElementById('assessmentForm');
  if (assessmentForm) {
    assessmentForm.addEventListener('input', updateLiveScore);
    assessmentForm.addEventListener('change', updateLiveScore);
    assessmentForm.addEventListener('submit', (event) => {
      event.preventDefault();
      if (validateForm()) {
        assessmentForm.submit();
      }
    });
  }

  if (!rubricName || typeof rubricName !== 'string' || !rubricName.trim()) {
    showFormError('No rubric was provided for this interview.');
    return;
  }

  const rootPath = getRootPath();
  const rubricUrl = buildRubricUrl(rubricName, rootPath);

  try {
    const response = await fetch(rubricUrl, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    rubricData = await response.json();
    renderRubric(rubricData);
  } catch (error) {
    console.error('Failed to load assessment rubric', error);
    showFormError('The assessment rubric could not be loaded. Please refresh and try again.');
  }
}
