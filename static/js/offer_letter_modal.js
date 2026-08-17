async function openOfferLetter(url, role) {
  const today = new Date();
  document.getElementById('letterDate').textContent =
    today.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  document.getElementById('letterLoading').style.display = 'block';
  document.getElementById('letterGeneratedText').style.display = 'none';
  document.getElementById('letterError').style.display = 'none';
  document.getElementById('copiedMsg').style.display = 'none';
  document.getElementById('offerModal').classList.add('active');

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        job_position: role || '',
        reporting_to: '',
        salary: '',
      }),
    });

    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    const data = await response.json();

    document.getElementById('letterLoading').style.display = 'none';
    document.getElementById('letterGeneratedText').innerHTML = formatOfferLetter(data.letter);
    document.getElementById('letterGeneratedText').style.display = 'block';
  } catch (err) {
    document.getElementById('letterLoading').style.display = 'none';
    document.getElementById('letterError').textContent = 'Failed to generate offer letter. Please try again.';
    document.getElementById('letterError').style.display = 'block';
    console.error('Offer letter generation failed', err);
  }
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
}

function formatOfferLetter(letter) {
  const rows = [
    ['Candidate name', /^(candidate\s+name)\s*:\s*(.*)$/i],
    ['Candidate email', /^(candidate\s+email)\s*:\s*(.*)$/i],
    ['Job Position info', /^(job\s+position\s+info)\s*:\s*(.*)$/i],
    ['Job position', /^(job\s+position)\s*:\s*(.*)$/i],
    ['Reporting To', /^(reporting\s+to)\s*:\s*(.*)$/i],
    ['Salary', /^(salary)\s*:?\s*(.*)$/i],
  ];
  const details = {};
  const content = [];

  letter.split(/\r?\n/).forEach(line => {
    const trimmed = line.trim();
    if (/^summary\s*:?$/i.test(trimmed)) return;

    const matched = rows.find(([, pattern]) => pattern.test(trimmed));
    if (matched) {
      const match = matched[1].exec(trimmed);
      details[matched[0]] = match[2].trim();
    } else {
      content.push(line);
    }
  });

  const summary = content.join('\n').replace(/^\s+|\s+$/g, '');
  const summaryHtml = escapeHtml(summary).replace(/\n/g, '<br>');
  const tableRows = rows.map(([label]) => `
    <tr><th style="width:36%;border:1px solid #777;padding:2px 6px;text-align:left;font-weight:${label === 'Job Position info' ? '700' : '400'};">${escapeHtml(label)}</th><td style="border:1px solid #777;padding:2px 6px;text-align:left;">${escapeHtml(details[label] || '')}</td></tr>
  `).join('');

  return `${summaryHtml}<table class="offer-details-table" style="width:100%;margin-top:34px;border-collapse:collapse;"><tbody>${tableRows}</tbody></table>`;
}

function closeModal() {
  document.getElementById('offerModal').classList.remove('active');
}

function copyLetter() {
  const letter = document.getElementById('letterGeneratedText');
  const plainText = letter.innerText;
  const htmlText = `<div style="font-family:Arial,sans-serif;line-height:1.6;">${letter.innerHTML}</div>`;
  const copyPromise = navigator.clipboard && window.ClipboardItem
    ? navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([htmlText], { type: 'text/html' }),
          'text/plain': new Blob([plainText], { type: 'text/plain' }),
        }),
      ])
    : navigator.clipboard.writeText(plainText);

  copyPromise.then(function () {
    const msg = document.getElementById('copiedMsg');
    msg.style.display = 'inline';
    setTimeout(() => { msg.style.display = 'none'; }, 2500);
  }).catch(function () {
    const range = document.createRange();
    range.selectNodeContents(letter);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand('copy');
    selection.removeAllRanges();
  });
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.offer-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openOfferLetter(btn.dataset.generateUrl, btn.dataset.role);
    });
  });

  const overlay = document.getElementById('offerModal');
  if (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === this) closeModal();
    });
  }
});