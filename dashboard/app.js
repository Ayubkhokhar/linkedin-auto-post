/* ═══════════════════════════════════════════════════════
   LinkedIn Auto-Post Dashboard — App Logic
   Uses GitHub API to read history, trigger workflows,
   and display status.
   ═══════════════════════════════════════════════════════ */

// ── STATE ─────────────────────────────────────────────────────────
const state = {
  owner: '',
  repo:  '',
  pat:   '',
  history: null,
  selectedPostType: '',
};

const POST_TYPE_COLORS = {
  dev_tip:            { bg: 'var(--purple-dim)',  color: 'var(--purple-light)', label: 'Dev Tip' },
  client_story:       { bg: 'var(--blue-dim)',    color: 'var(--blue-light)',   label: 'Client Story' },
  tech_discovery:     { bg: 'var(--teal-dim)',    color: '#2dd4bf',             label: 'Tech Discovery' },
  dev_journey:        { bg: 'var(--green-dim)',   color: 'var(--green-light)',  label: 'Dev Journey' },
  debugging_story:    { bg: 'var(--orange-dim)',  color: 'var(--orange)',       label: 'Debug Story' },
  community_question: { bg: 'var(--pink-dim)',    color: '#f472b6',             label: 'Community Q' },
};

const SCHEDULE_UTC = [7, 12, 18];  // hours in UTC

// ── INIT ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSavedConfig();
  setupNavigation();
  setupTypePills();
  updateSchedule();
  setInterval(updateSchedule, 60000);
  updateNextPostCountdown();
  setInterval(updateNextPostCountdown, 1000);

  if (state.owner && state.repo && state.pat) {
    loadHistory();
    checkWorkflowStatus();
  } else {
    setStatus('unconfigured', 'Not configured');
  }
});

// ── NAVIGATION ─────────────────────────────────────────────────────
function setupNavigation() {
  const links = document.querySelectorAll('.nav-link');
  links.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const section = link.dataset.section;
      activateSection(section);
    });
  });

  document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
}

function activateSection(name) {
  // Update nav links
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  const activeLink = document.getElementById(`nav-${name}`);
  if (activeLink) activeLink.classList.add('active');

  // Update sections
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  const activeSection = document.getElementById(`section-${name}`);
  if (activeSection) activeSection.classList.add('active');

  // Update page title
  const titles = {
    dashboard: 'Dashboard',
    preview:   'Preview Post',
    history:   'Post History',
    topics:    'Topics',
    trigger:   'Manual Post',
    setup:     'Setup Guide',
  };
  document.getElementById('pageTitle').textContent = titles[name] || name;

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');

  // Load data for section
  if (name === 'history') loadHistory();
}

// ── CONFIG PERSISTENCE ──────────────────────────────────────────────
function loadSavedConfig() {
  state.owner = localStorage.getItem('gh_owner') || '';
  state.repo  = localStorage.getItem('gh_repo')  || '';
  state.pat   = localStorage.getItem('gh_pat')   || '';

  document.getElementById('ghOwner').value = state.owner;
  document.getElementById('ghRepo').value  = state.repo;
  document.getElementById('ghPat').value   = state.pat ? '••••••••••••••' : '';
}

function saveGithubConfig() {
  const owner = document.getElementById('ghOwner').value.trim();
  const repo  = document.getElementById('ghRepo').value.trim();
  const pat   = document.getElementById('ghPat').value.trim();

  if (!owner || !repo || !pat || pat === '••••••••••••••') {
    showToast('Please fill in GitHub username, repo name, and PAT', 'error');
    return;
  }

  state.owner = owner;
  state.repo  = repo;
  state.pat   = pat;

  localStorage.setItem('gh_owner', owner);
  localStorage.setItem('gh_repo',  repo);
  localStorage.setItem('gh_pat',   pat);

  document.getElementById('ghPat').value = '••••••••••••••';

  showToast('Config saved! Loading data...', 'success');
  loadHistory();
  checkWorkflowStatus();
}

// ── GITHUB API HELPERS ──────────────────────────────────────────────
function ghHeaders() {
  return {
    'Authorization': `Bearer ${state.pat}`,
    'Accept':        'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

async function ghGet(path) {
  const resp = await fetch(`https://api.github.com/repos/${state.owner}/${state.repo}${path}`, {
    headers: ghHeaders(),
  });
  if (!resp.ok) throw new Error(`GitHub API ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function ghPost(path, body) {
  const resp = await fetch(`https://api.github.com/repos/${state.owner}/${state.repo}${path}`, {
    method:  'POST',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  return resp;
}

// ── LOAD POST HISTORY ───────────────────────────────────────────────
async function loadHistory() {
  if (!state.owner || !state.repo || !state.pat) return;

  try {
    // Fetch post_history.json from GitHub
    const resp = await ghGet('/contents/data/post_history.json');
    const content = JSON.parse(atob(resp.content.replace(/\n/g, '')));
    state.history = content;

    renderStats(content);
    renderRecentPosts(content.posts?.slice(-5).reverse() || []);
    renderHistoryGrid(content.posts || []);

  } catch (err) {
    console.error('Failed to load history:', err);
    if (err.message.includes('404')) {
      renderStats({ posts: [], total_posts: 0 });
      renderRecentPosts([]);
      renderHistoryGrid([]);
    }
  }
}

// ── RENDER STATS ────────────────────────────────────────────────────
function renderStats(data) {
  const posts = data.posts || [];

  // Today's posts
  const today = new Date().toISOString().slice(0, 10);
  const todayPosts = posts.filter(p => p.timestamp?.startsWith(today)).length;
  animateCount('postsToday', todayPosts);
  animateCount('postsTotal', posts.length);

  // Streak
  const streak = calculateStreak(posts);
  animateCount('streakDays', streak);
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = parseInt(el.textContent) || 0;
  const diff  = target - start;
  const steps = 20;
  let current = 0;
  const timer = setInterval(() => {
    current++;
    el.textContent = Math.round(start + (diff * current / steps));
    if (current >= steps) clearInterval(timer);
  }, 30);
}

function calculateStreak(posts) {
  if (!posts.length) return 0;
  const days = new Set(posts.map(p => p.timestamp?.slice(0, 10)));
  let streak = 0;
  const d = new Date();
  while (true) {
    const key = d.toISOString().slice(0, 10);
    if (days.has(key)) {
      streak++;
      d.setDate(d.getDate() - 1);
    } else break;
  }
  return streak;
}

// ── RENDER POSTS ────────────────────────────────────────────────────
function renderRecentPosts(posts) {
  const container = document.getElementById('recentPosts');
  if (!posts.length) {
    container.innerHTML = '<div class="empty-state"><p>No posts yet. Set up secrets and push to GitHub.</p></div>';
    return;
  }

  container.innerHTML = posts.map(post => {
    const meta = POST_TYPE_COLORS[post.post_type] || { bg: 'var(--bg-input)', color: 'var(--text-muted)', label: post.post_type };
    const date = post.timestamp ? new Date(post.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
    const tags = (post.hashtags || []).slice(0, 3).map(t => `<span class="post-tag">#${t}</span>`).join('');
    const preview = (post.text_preview || '').slice(0, 120) + (post.text_preview?.length > 120 ? '...' : '');

    return `
      <div class="post-item" onclick="openLinkedInPost('${post.linkedin_url || ''}')">
        <div class="post-item-top">
          <span class="post-type-badge" style="background:${meta.bg};color:${meta.color}">${meta.label}</span>
          <span class="post-item-date">${date}</span>
        </div>
        <div class="post-item-text">${escHtml(preview)}</div>
        <div class="post-item-tags">${tags}</div>
      </div>
    `;
  }).join('');
}

function renderHistoryGrid(posts) {
  const container = document.getElementById('historyGrid');
  if (!posts.length) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>
        <p>No post history found. Posts will appear here after the first run.</p>
      </div>
    `;
    return;
  }

  const sorted = [...posts].reverse();
  container.innerHTML = sorted.map(post => {
    const meta = POST_TYPE_COLORS[post.post_type] || { bg: 'var(--bg-input)', color: 'var(--text-muted)', label: post.post_type };
    const date = post.timestamp ? new Date(post.timestamp).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
    const tags = (post.hashtags || []).slice(0, 4).map(t => `<span class="post-tag" style="font-size:11px">#${t}</span>`).join('');
    const preview = (post.text_preview || '').slice(0, 160) + ((post.text_preview || '').length > 160 ? '...' : '');
    const linkHtml = post.linkedin_url ? `<a class="history-card-link" href="${post.linkedin_url}" target="_blank">View on LinkedIn →</a>` : '';

    return `
      <div class="history-card">
        <div class="history-card-top">
          <span class="post-type-badge" style="background:${meta.bg};color:${meta.color}">${meta.label}</span>
          <span class="history-card-date">${date}</span>
        </div>
        <div class="history-card-text">${escHtml(preview)}</div>
        <div class="history-card-footer">
          <div class="history-card-tags">${tags}</div>
          ${linkHtml}
        </div>
      </div>
    `;
  }).join('');
}

// ── SCHEDULE DISPLAY ────────────────────────────────────────────────
function updateSchedule() {
  const now = new Date();
  const nowUTC = now.getUTCHours() * 60 + now.getUTCMinutes();

  SCHEDULE_UTC.forEach((hour, i) => {
    const slotMinutes = hour * 60;
    const idx = i + 1;
    const statusEl  = document.getElementById(`sch-status-${idx}`);
    const progEl    = document.getElementById(`prog-${idx}`);

    if (nowUTC > slotMinutes + 30) {
      // Done for today
      statusEl.textContent = 'Done';
      statusEl.className   = 'schedule-status done';
      progEl.style.width   = '100%';
    } else if (nowUTC >= slotMinutes - 5 && nowUTC <= slotMinutes + 30) {
      // Currently running
      statusEl.textContent = 'Running';
      statusEl.className   = 'schedule-status active';
      progEl.style.width   = '60%';
    } else {
      statusEl.textContent = 'Upcoming';
      statusEl.className   = 'schedule-status';
      const totalDay = 24 * 60;
      const prog = Math.min(100, Math.max(0, (nowUTC / slotMinutes) * 30));
      progEl.style.width   = `${prog}%`;
    }
  });
}

function updateNextPostCountdown() {
  const now = new Date();
  const utcH = now.getUTCHours();
  const utcM = now.getUTCMinutes();
  const nowMins = utcH * 60 + utcM;

  let nextUTC = null;
  for (const h of SCHEDULE_UTC) {
    if (h * 60 > nowMins + 5) {
      nextUTC = h;
      break;
    }
  }
  if (nextUTC === null) nextUTC = SCHEDULE_UTC[0]; // tomorrow

  const nextMins = nextUTC * 60;
  let diffMins = nextMins - nowMins;
  if (diffMins < 0) diffMins += 24 * 60;

  const h = Math.floor(diffMins / 60);
  const m = diffMins % 60;

  // PKT = UTC + 5
  const pktH = (nextUTC + 5) % 24;
  const pktStr = `${String(pktH).padStart(2, '0')}:00`;

  document.getElementById('nextPostTime').textContent = pktStr;
}

// ── WORKFLOW TRIGGER ────────────────────────────────────────────────
async function checkWorkflowStatus() {
  if (!state.owner || !state.repo || !state.pat) return;
  try {
    const runs = await ghGet('/actions/runs?per_page=3&workflow_id=post.yml');
    const latest = runs.workflow_runs?.[0];

    if (!latest) {
      setStatus('loading', 'No runs yet');
      return;
    }

    if (latest.status === 'completed') {
      if (latest.conclusion === 'success') {
        setStatus('online', 'Automation active');
      } else {
        setStatus('offline', `Last run: ${latest.conclusion}`);
      }
    } else {
      setStatus('loading', 'Running now...');
    }
  } catch (e) {
    setStatus('offline', 'Cannot reach GitHub');
  }
}

function setStatus(type, text) {
  const dot  = document.getElementById('statusDot');
  const label = document.getElementById('statusText');
  dot.className  = `status-dot ${type}`;
  label.textContent = text;
}

async function triggerWorkflow(dryRun = false, hint = '') {
  if (!state.owner || !state.repo || !state.pat) {
    showToast('Please save your GitHub config first', 'error');
    return null;
  }

  const resp = await ghPost('/actions/workflows/post.yml/dispatches', {
    ref: 'main',
    inputs: {
      dry_run:    dryRun ? 'true' : 'false',
      topic_hint: hint,
    },
  });

  return resp.ok || resp.status === 204;
}

async function triggerPreview() {
  const btn  = document.getElementById('previewBtn');
  const hint = document.getElementById('previewHint').value.trim();

  btn.disabled = true;
  btn.textContent = 'Triggering...';

  const ok = await triggerWorkflow(true, hint);

  if (ok) {
    const actionsUrl = `https://github.com/${state.owner}/${state.repo}/actions/workflows/post.yml`;
    document.getElementById('actionsLink').href    = actionsUrl;
    document.getElementById('actionsLink').style.display = 'inline-flex';
    document.getElementById('previewResult').style.display = 'block';
    document.getElementById('previewText').textContent = 
      'The dry-run workflow has been triggered. Open the GitHub Actions link to see the generated post content in the logs (usually ready in 30-60 seconds).';
    showToast('Dry-run triggered! Check GitHub Actions.', 'success');
  } else {
    showToast('Failed to trigger workflow. Check your config.', 'error');
  }

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg> Generate Preview`;
}

async function triggerLivePost() {
  const btn    = document.getElementById('triggerBtn');
  const status = document.getElementById('triggerStatus');
  const hint   = document.getElementById('triggerHint').value.trim();

  if (!state.owner || !state.repo || !state.pat) {
    showToast('Please save your GitHub config first (top bar)', 'error');
    return;
  }

  if (!confirm('This will publish a real post to your LinkedIn profile right now. Continue?')) return;

  btn.disabled = true;
  btn.textContent = 'Posting...';

  status.style.display = 'block';
  status.className     = 'trigger-status loading';
  status.textContent   = 'Triggering GitHub Actions workflow...';

  const ok = await triggerWorkflow(false, hint);

  if (ok) {
    status.className   = 'trigger-status success';
    status.innerHTML   = `
      ✓ Workflow triggered! Your LinkedIn post is being generated and published now.
      <br><br>
      <a href="https://github.com/${state.owner}/${state.repo}/actions/workflows/post.yml" 
         target="_blank" style="color:var(--green-light);text-decoration:underline">
        View workflow run →
      </a>
      <br><br>
      The post history will update in about 60-90 seconds. Refresh the History tab after that.
    `;
    showToast('Live post triggered! Check LinkedIn in ~60 seconds.', 'success');
    checkWorkflowStatus();
  } else {
    status.className = 'trigger-status error';
    status.textContent = '✗ Failed to trigger workflow. Check your GitHub PAT permissions (needs "repo" + "workflow" scopes).';
    showToast('Trigger failed. Check config.', 'error');
  }

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd"/></svg> Post Now`;
}

// ── TYPE PILLS ──────────────────────────────────────────────────────
function setupTypePills() {
  document.querySelectorAll('.type-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.type-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.selectedPostType = pill.dataset.type || '';
    });
  });
}

// ── UTILITY ─────────────────────────────────────────────────────────
function openLinkedInPost(url) {
  if (url) window.open(url, '_blank');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function copyCode(btn) {
  const code = btn.previousElementSibling.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
}

function showToast(msg, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className   = `toast ${type} show`;
  setTimeout(() => { toast.className = `toast ${type}`; }, 3500);
}
