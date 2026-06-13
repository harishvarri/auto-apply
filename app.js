// Application State
let jobs = [];
let userProfile = null;
let selectedJobId = null;

// DOM Elements
const jobsListEl = document.getElementById('jobsList');
const detailsPanelEl = document.getElementById('detailsPanel');
const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');
const sortControl = document.getElementById('sortControl');
const runScraperBtn = document.getElementById('runScraperBtn');
const batchApplyBtn = document.getElementById('batchApplyBtn');
const profileForm = document.getElementById('profileForm');
const toastEl = document.getElementById('toast');
const quickApplyBtn = document.getElementById('quickApplyBtn');
const parseResumeBtn = document.getElementById('parseResumeBtn');
const parseResumeProfileBtn = document.getElementById('parseResumeProfileBtn');

// Stats Elements
const statTotalEl = document.getElementById('statTotal');
const statAppliedEl = document.getElementById('statApplied');
const statPendingEl = document.getElementById('statPending');
const statMatchEl = document.getElementById('statMatch');

// India DOM Elements
const indiaJobsListEl = document.getElementById('indiaJobsList');
const indiaDetailsPanelEl = document.getElementById('indiaDetailsPanel');
const indiaSearchInput = document.getElementById('indiaSearchInput');
const indiaStatusFilter = document.getElementById('indiaStatusFilter');
const indiaSortControl = document.getElementById('indiaSortControl');
const indiaBatchApplyBtn = document.getElementById('indiaBatchApplyBtn');

// India Stats Elements
const indiaStatTotalEl = document.getElementById('indiaStatTotal');
const indiaStatAppliedEl = document.getElementById('indiaStatApplied');
const indiaStatPendingEl = document.getElementById('indiaStatPending');
const indiaStatMatchEl = document.getElementById('indiaStatMatch');

let selectedIndiaJobId = null;

// Navigation Tabs
const navItems = document.querySelectorAll('.nav-item');
const tabs = document.querySelectorAll('.tab-content');

navItems.forEach(item => {
    item.addEventListener('click', () => {
        navItems.forEach(n => n.classList.remove('active'));
        tabs.forEach(t => t.classList.remove('active'));
        
        item.classList.add('active');
        const tabId = item.getAttribute('data-tab') + 'Tab';
        document.getElementById(tabId).classList.add('active');
    });
});

// Toast Notification Helper
function showToast(message, isError = false) {
    toastEl.innerText = message;
    toastEl.style.borderLeftColor = isError ? 'var(--warning)' : 'var(--primary)';
    toastEl.classList.add('show');
    setTimeout(() => {
        toastEl.classList.remove('show');
    }, 3500);
}

// Check Server Status
async function checkServerStatus() {
    try {
        const response = await fetch('/jobs_database.json?t=' + Date.now());
        if (response.ok) {
            document.querySelector('.status-dot').classList.add('online');
            document.getElementById('serverStatusText').innerText = "System Operational";
        }
    } catch (e) {
        document.querySelector('.status-dot').classList.remove('online');
        document.getElementById('serverStatusText').innerText = "Offline Mode";
    }
}

// Load Data
async function loadData() {
    try {
        // Load Profile
        const profileRes = await fetch('/profile.json');
        if (profileRes.ok) {
            userProfile = await profileRes.json();
            populateProfileForm();
        }
        
        // Load Jobs
        const jobsRes = await fetch('/jobs_database.json?t=' + Date.now());
        if (jobsRes.ok) {
            jobs = await jobsRes.json();
            renderStats();
            filterAndRenderJobs();
            filterAndRenderIndiaJobs();
            renderCustomJobs();
        }
    } catch (e) {
        showToast("Error loading databases. Please run server.py", true);
        console.error(e);
    }
}

// Populate Profile Form
function populateProfileForm() {
    if (!userProfile) return;
    const personal = userProfile.personal;
    
    // Fill basic fields
    for (const key in personal) {
        const input = profileForm.querySelector(`[name="${key}"]`);
        if (input) {
            input.value = personal[key];
        }
    }
    
    // Fill custom responses fields
    const custom = userProfile.custom_responses || {};
    for (const key in custom) {
        const input = profileForm.querySelector(`[name="custom_${key}"]`);
        if (input) {
            input.value = custom[key];
        }
    }
    
    // Render custom keywords
    renderCustomKeywordsTable();
}

// Render Custom Keywords Table
function renderCustomKeywordsTable() {
    const tableBody = document.getElementById('keywordsTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '';
    
    const customKeywords = (userProfile && userProfile.custom_keywords) || {};
    const keys = Object.keys(customKeywords);
    
    if (keys.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="3" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
                    No custom keyword mappings configured. Add one below!
                </td>
            </tr>
        `;
        return;
    }
    
    keys.forEach(keyword => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight: 600; font-family: monospace;">${escapeHtml(keyword)}</td>
            <td style="color: var(--text-secondary); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(customKeywords[keyword])}</td>
            <td style="text-align: center;">
                <button type="button" class="btn-delete-keyword" onclick="deleteKeywordMapping('${escapeSingleQuote(keyword)}')">Delete</button>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeSingleQuote(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'");
}

function safeUrl(url) {
    if (!url) return '#';
    const trimmed = url.trim();
    if (trimmed.startsWith('https://') || trimmed.startsWith('http://')) return trimmed;
    return '#';
}

// Global delete keyword mapping callback
window.deleteKeywordMapping = function(keyword) {
    if (userProfile && userProfile.custom_keywords && userProfile.custom_keywords[keyword]) {
        delete userProfile.custom_keywords[keyword];
        renderCustomKeywordsTable();
        showToast("Keyword mapping removed! Click Save Profile Settings to save.");
    }
};

// Render Stats Card
function renderStats() {
    if (!jobs.length) return;
    
    // Global stats: jobs that are NOT India jobs
    const globalJobs = jobs.filter(j => !isIndiaJob(j));
    const total = globalJobs.length;
    const applied = globalJobs.filter(j => j.status === 'Applied').length;
    const pending = globalJobs.filter(j => j.status === 'Pending' || !j.status).length;
    const sumMatch = globalJobs.reduce((sum, j) => sum + (j.match_rate || 70), 0);
    const avgMatch = total ? Math.round(sumMatch / total) : 0;
    
    statTotalEl.innerText = total;
    statAppliedEl.innerText = applied;
    statPendingEl.innerText = pending;
    statMatchEl.innerText = `${avgMatch}%`;

    // India stats: jobs that ARE India jobs
    const indiaJobs = jobs.filter(j => isIndiaJob(j));
    const indiaTotal = indiaJobs.length;
    const indiaApplied = indiaJobs.filter(j => j.status === 'Applied').length;
    const indiaPending = indiaJobs.filter(j => j.status === 'Pending' || !j.status).length;
    const indiaSumMatch = indiaJobs.reduce((sum, j) => sum + (j.match_rate || 70), 0);
    const indiaAvgMatch = indiaTotal ? Math.round(indiaSumMatch / indiaTotal) : 0;

    indiaStatTotalEl.innerText = indiaTotal;
    indiaStatAppliedEl.innerText = indiaApplied;
    indiaStatPendingEl.innerText = indiaPending;
    indiaStatMatchEl.innerText = `${indiaAvgMatch}%`;
}

// Helper to identify India-based jobs
function isIndiaJob(job) {
    if (!job || !job.location) return false;
    const loc = job.location.toLowerCase();
    // Exclude US locations like Indianapolis or Indiana that contain "india"
    const hasIndiaWord = loc.includes('india') && !loc.includes('indianapolis') && !loc.includes('indiana');
    return hasIndiaWord || 
           loc.includes('bengaluru') || 
           loc.includes('bangalore') || 
           loc.includes('hyderabad') || 
           loc.includes('pune') || 
           loc.includes('mumbai') || 
           loc.includes('noida') || 
           loc.includes('gurugram') || 
           loc.includes('gurgaon') || 
           loc.includes('chennai');
}

// Filter and Render Jobs List (Global/Non-India Jobs)
function filterAndRenderJobs() {
    const searchTerm = searchInput.value.toLowerCase();
    const selectedStatus = statusFilter.value;
    const sortBy = sortControl.value;
    
    let filtered = jobs.filter(job => {
        // Exclude India jobs from global tab
        if (isIndiaJob(job)) return false;

        const matchesSearch = 
            job.title.toLowerCase().includes(searchTerm) ||
            job.company.toLowerCase().includes(searchTerm) ||
            job.skills_required.some(s => s.toLowerCase().includes(searchTerm));
            
        const matchesStatus = 
            selectedStatus === 'all' || 
            job.status === selectedStatus ||
            (selectedStatus === 'Pending' && !job.status);
            
        return matchesSearch && matchesStatus;
    });
    
    // Sort
    if (sortBy === 'match_desc') {
        filtered.sort((a, b) => (b.match_rate || 70) - (a.match_rate || 70));
    } else if (sortBy === 'title_asc') {
        filtered.sort((a, b) => a.title.localeCompare(b.title));
    }
    
    jobsListEl.innerHTML = '';
    
    if (filtered.length === 0) {
        jobsListEl.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--text-muted);">
                No jobs found matching filters.
            </div>
        `;
        return;
    }
    
    filtered.forEach(job => {
        const item = document.createElement('div');
        item.className = `job-item ${selectedJobId === job.id ? 'selected' : ''}`;
        item.addEventListener('click', () => selectJob(job.id));
        
        const isApplied = job.status === 'Applied';
        const badgeClass = isApplied ? 'applied' : 'pending';
        const badgeText = isApplied ? 'Applied' : 'Pending';
        
        item.innerHTML = `
            <div class="job-meta-main">
                <h3>${job.title}</h3>
                <p>${job.company} • ${job.location}</p>
            </div>
            <div class="job-meta-side">
                <span class="badge ${badgeClass}">${badgeText}</span>
                <span class="match-badge">${job.match_rate || 70}% Match</span>
            </div>
        `;
        
        jobsListEl.appendChild(item);
    });
}

// Filter and Render India Jobs List
function filterAndRenderIndiaJobs() {
    const searchTerm = indiaSearchInput.value.toLowerCase();
    const selectedStatus = indiaStatusFilter.value;
    const sortBy = indiaSortControl.value;
    
    let filtered = jobs.filter(job => {
        // Exclusively show India jobs in the India tab
        if (!isIndiaJob(job)) return false;

        const matchesSearch = 
            job.title.toLowerCase().includes(searchTerm) ||
            job.company.toLowerCase().includes(searchTerm) ||
            job.skills_required.some(s => s.toLowerCase().includes(searchTerm));
            
        const matchesStatus = 
            selectedStatus === 'all' || 
            job.status === selectedStatus ||
            (selectedStatus === 'Pending' && !job.status);
            
        return matchesSearch && matchesStatus;
    });
    
    // Sort
    if (sortBy === 'match_desc') {
        filtered.sort((a, b) => (b.match_rate || 70) - (a.match_rate || 70));
    } else if (sortBy === 'title_asc') {
        filtered.sort((a, b) => a.title.localeCompare(b.title));
    }
    
    indiaJobsListEl.innerHTML = '';
    
    if (filtered.length === 0) {
        indiaJobsListEl.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--text-muted);">
                No India-based jobs found matching filters.
            </div>
        `;
        return;
    }
    
    filtered.forEach(job => {
        const item = document.createElement('div');
        item.className = `job-item ${selectedIndiaJobId === job.id ? 'selected' : ''}`;
        item.addEventListener('click', () => selectIndiaJob(job.id));
        
        const isApplied = job.status === 'Applied';
        const badgeClass = isApplied ? 'applied' : 'pending';
        const badgeText = isApplied ? 'Applied' : 'Pending';
        
        item.innerHTML = `
            <div class="job-meta-main">
                <h3>${job.title}</h3>
                <p>${job.company} • ${job.location}</p>
            </div>
            <div class="job-meta-side">
                <span class="badge ${badgeClass}">${badgeText}</span>
                <span class="match-badge">${job.match_rate || 70}% Match</span>
            </div>
        `;
        
        indiaJobsListEl.appendChild(item);
    });
}

// Select India Job and Render Details
function selectIndiaJob(jobId) {
    selectedIndiaJobId = jobId;
    
    // Highlight in list
    document.querySelectorAll('#indiaJobsList .job-item').forEach(el => el.classList.remove('selected'));
    const job = jobs.find(j => j.id === jobId);
    
    if (!job) return;
    
    // Render Detail Pane
    const skillsList = userProfile ? userProfile.skills : {};
    const userSkillsFlattened = Object.values(skillsList).flat().map(s => s.toLowerCase());
    
    const tagsHtml = job.skills_required.map(skill => {
        const isMatched = userSkillsFlattened.includes(skill.toLowerCase());
        const tagClass = isMatched ? 'tag match' : 'tag';
        const checkIcon = isMatched ? '✓ ' : '';
        return `<span class="${tagClass}">${checkIcon}${skill}</span>`;
    }).join(' ');
    
    const applyButtonText = job.status === 'Applied' ? 'Apply Again (Autofill)' : '🚀 Auto-Fill in Browser';
    const applyButtonClass = job.status === 'Applied' ? 'btn btn-secondary' : 'btn btn-primary';
    
    indiaDetailsPanelEl.innerHTML = `
        <div class="detail-header">
            <h2>${escapeHtml(job.title)}</h2>
            <div class="company">${escapeHtml(job.company)}</div>
            <div class="meta-row">
                <span>📍 ${escapeHtml(job.location)}</span>
                <span>📅 Posted: ${escapeHtml(job.date_posted || 'June 2026')}</span>
                <span>ℹ️ Source: ${escapeHtml(job.source || 'Portal')}</span>
            </div>
        </div>

        <div class="detail-body">
            <div class="detail-section">
                <h4>Match Quality Analysis</h4>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent-cyan); margin-bottom: 0.25rem;">
                    ${parseInt(job.match_rate) || 70}% Match
                </div>
                <p style="font-size: 0.85rem;">Based on your B.Tech CSE (AI) credentials, internships, and skill matching.</p>
            </div>

            <div class="detail-section">
                <h4>Required Skills</h4>
                <div class="skills-tags">
                    ${tagsHtml}
                </div>
            </div>

            <div class="detail-section">
                <h4>Job Description Summary</h4>
                <p>${escapeHtml(job.description)}</p>
            </div>

            <div class="actions-section">
                <button id="indiaApplyBtn" class="${applyButtonClass}" style="width: 100%; font-size: 1rem; padding: 0.9rem;">
                    ${applyButtonText}
                </button>
                <a href="${safeUrl(job.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="width: 100%;">
                    🌐 Open Direct Job Link
                </a>
                <button id="indiaMarkAppliedBtn" class="btn btn-success" style="width: 100%;">
                    ✅ Toggle Applied Status
                </button>
            </div>
        </div>
    `;
    
    // Add Click Listeners
    document.getElementById('indiaApplyBtn').addEventListener('click', () => runAutofill(job.id));
    document.getElementById('indiaMarkAppliedBtn').addEventListener('click', () => toggleJobAppliedStatus(job.id));
    
    // Highlight this job specifically
    const items = indiaJobsListEl.querySelectorAll('.job-item');
    jobs.filter(j => isIndiaJob(j)).forEach((j, idx) => {
        if (j.id === jobId && items[idx]) {
            items[idx].classList.add('selected');
        }
    });
}

// Select Job and Render Details
function selectJob(jobId) {
    selectedJobId = jobId;
    
    // Highlight in list
    document.querySelectorAll('.job-item').forEach(el => el.classList.remove('selected'));
    const jobItems = jobsListEl.children;
    const job = jobs.find(j => j.id === jobId);
    
    if (!job) return;
    
    // Render Detail Pane
    const skillsList = userProfile ? userProfile.skills : {};
    // Flatten user skills
    const userSkillsFlattened = Object.values(skillsList).flat().map(s => s.toLowerCase());
    
    const tagsHtml = job.skills_required.map(skill => {
        const isMatched = userSkillsFlattened.includes(skill.toLowerCase());
        const tagClass = isMatched ? 'tag match' : 'tag';
        const checkIcon = isMatched ? '✓ ' : '';
        return `<span class="${tagClass}">${checkIcon}${skill}</span>`;
    }).join(' ');
    
    const applyButtonText = job.status === 'Applied' ? 'Apply Again (Autofill)' : '🚀 Auto-Fill in Browser';
    const applyButtonClass = job.status === 'Applied' ? 'btn btn-secondary' : 'btn btn-primary';
    
    detailsPanelEl.innerHTML = `
        <div class="detail-header">
            <h2>${escapeHtml(job.title)}</h2>
            <div class="company">${escapeHtml(job.company)}</div>
            <div class="meta-row">
                <span>📍 ${escapeHtml(job.location)}</span>
                <span>📅 Posted: ${escapeHtml(job.date_posted || 'June 2026')}</span>
                <span>ℹ️ Source: ${escapeHtml(job.source || 'Portal')}</span>
            </div>
        </div>

        <div class="detail-body">
            <div class="detail-section">
                <h4>Match Quality Analysis</h4>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent-cyan); margin-bottom: 0.25rem;">
                    ${parseInt(job.match_rate) || 70}% Match
                </div>
                <p style="font-size: 0.85rem;">Based on your B.Tech CSE (AI) credentials, internships, and skill matching.</p>
            </div>

            <div class="detail-section">
                <h4>Required Skills</h4>
                <div class="skills-tags">
                    ${tagsHtml}
                </div>
            </div>

            <div class="detail-section">
                <h4>Job Description Summary</h4>
                <p>${escapeHtml(job.description)}</p>
            </div>

            <div class="actions-section">
                <button id="applyBtn" class="${applyButtonClass}" style="width: 100%; font-size: 1rem; padding: 0.9rem;">
                    ${applyButtonText}
                </button>
                <a href="${safeUrl(job.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="width: 100%;">
                    🌐 Open Direct Job Link
                </a>
                <button id="markAppliedBtn" class="btn btn-success" style="width: 100%;">
                    ✅ Toggle Applied Status
                </button>
            </div>
        </div>
    `;
    
    // Add Click Listeners
    document.getElementById('applyBtn').addEventListener('click', () => runAutofill(job.id));
    document.getElementById('markAppliedBtn').addEventListener('click', () => toggleJobAppliedStatus(job.id));
    
    // Re-render select styles on lists
    filterAndRenderJobs();
}

// Launch Playwright Applier
async function runAutofill(jobId) {
    showToast("Launching automation browser... Please check your system tasks!");
    try {
        const res = await fetch('/api/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId })
        });
        
        if (res.ok) {
            const data = await res.json();
            showToast("Autofill launched. Follow prompts in command terminal!");
            
            // Poll for updates to database.json (since the playwright script writes to database when applied)
            setTimeout(async () => {
                await loadData();
                if (selectedJobId) selectJob(selectedJobId);
                if (selectedIndiaJobId) selectIndiaJob(selectedIndiaJobId);
            }, 10000); // refresh after 10s
        } else {
            showToast("Failed to launch autofill.", true);
        }
    } catch (e) {
        showToast("Error connecting to automation backend.", true);
    }
}

// Toggle Applied Status manually
function toggleJobAppliedStatus(jobId) {
    const job = jobs.find(j => j.id === jobId);
    if (!job) return;
    
    job.status = job.status === 'Applied' ? 'Pending' : 'Applied';
    
    renderStats();
    filterAndRenderJobs();
    filterAndRenderIndiaJobs();
    if (selectedJobId === jobId) {
        selectJob(jobId);
    }
    if (selectedIndiaJobId === jobId) {
        selectIndiaJob(jobId);
    }
    showToast(`Status updated to ${job.status}`);
}

// Refresh Jobs via Scraper
runScraperBtn.addEventListener('click', async () => {
    showToast("Triggering job scraper... fetching feeds.");
    runScraperBtn.disabled = true;
    runScraperBtn.innerText = "🔄 Scraping...";
    
    try {
        const res = await fetch('/api/run-scraper');
        if (res.ok) {
            showToast("Scraper running in background! Data will update soon.");
            
            // Poll for new data
            let attempts = 0;
            const interval = setInterval(async () => {
                attempts++;
                await loadData();
                if (attempts > 5) {
                    clearInterval(interval);
                    runScraperBtn.disabled = false;
                    runScraperBtn.innerText = "🔄 Refresh Jobs";
                }
            }, 3000);
        }
    } catch (e) {
        showToast("Error triggering scraper.", true);
        runScraperBtn.disabled = false;
        runScraperBtn.innerText = "🔄 Refresh Jobs";
    }
});

// Save Profile changes
profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(profileForm);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    
    // Add custom keywords dictionary
    data.custom_keywords = (userProfile && userProfile.custom_keywords) || {};
    
    try {
        const res = await fetch('/api/save-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (res.ok) {
            showToast("Resume profile saved successfully!");
            await loadData();
        } else {
            showToast("Failed to save profile details.", true);
        }
    } catch (e) {
        showToast("Error saving profile details.", true);
    }
});

// Add Keyword Mapping Click Listener
document.getElementById('addKeywordBtn').addEventListener('click', () => {
    const keywordInput = document.getElementById('newKeywordInput');
    const answerInput = document.getElementById('newAnswerInput');
    
    const keyword = keywordInput.value.trim();
    const answer = answerInput.value.trim();
    
    if (!keyword || !answer) {
        showToast("Please enter both keyword and answer.", true);
        return;
    }
    
    if (!userProfile) {
        userProfile = { personal: {}, custom_responses: {}, custom_keywords: {} };
    }
    if (!userProfile.custom_keywords) {
        userProfile.custom_keywords = {};
    }
    
    userProfile.custom_keywords[keyword] = answer;
    
    keywordInput.value = '';
    answerInput.value = '';
    
    renderCustomKeywordsTable();
    showToast("Keyword mapping added! Click Save Profile Settings to save.");
});

// Batch Apply Trigger
batchApplyBtn.addEventListener('click', async () => {
    let pendingJobs = jobs.filter(j => j.status === 'Pending' || !j.status);
    pendingJobs.sort((a, b) => (b.match_rate || 70) - (a.match_rate || 70));
    
    if (pendingJobs.length === 0) {
        showToast("No pending jobs found to apply!", true);
        return;
    }
    
    const selectedJobs = pendingJobs.slice(0, 10);
    const jobIds = selectedJobs.map(j => j.id);
    
    showToast(`Launching batch apply for ${selectedJobs.length} jobs in browser!`);
    
    batchApplyBtn.disabled = true;
    batchApplyBtn.innerText = "🚀 Applying Batch...";
    
    try {
        const res = await fetch('/api/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_ids: jobIds })
        });
        
        if (res.ok) {
            showToast("Batch launched! Watch the automation browser tabs process.");
            
            let pollCount = 0;
            const maxPolls = 120; // 6 minutes max safety limit
            
            const pollInterval = setInterval(async () => {
                pollCount++;
                await loadData();
                
                // Check if all batch jobs are processed
                const batchJobs = jobs.filter(j => jobIds.includes(j.id));
                const allProcessed = batchJobs.every(j => j.status && j.status !== 'Pending');
                
                if (allProcessed || pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    batchApplyBtn.disabled = false;
                    batchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
                    
                    const appliedCount = batchJobs.filter(j => j.status === 'Applied').length;
                    const reviewCount = batchJobs.filter(j => j.status === 'Review Required').length;
                    
                    showToast(`Batch Apply finished! Successful: ${appliedCount}, Review needed: ${reviewCount}`);
                }
            }, 3000);
        } else {
            showToast("Failed to launch batch apply.", true);
            batchApplyBtn.disabled = false;
            batchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
        }
    } catch (e) {
        showToast("Error connecting to automation backend.", true);
        batchApplyBtn.disabled = false;
        batchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
    }
});

// India Batch Apply Trigger
indiaBatchApplyBtn.addEventListener('click', async () => {
    let pendingJobs = jobs.filter(j => isIndiaJob(j) && (j.status === 'Pending' || !j.status));
    pendingJobs.sort((a, b) => (b.match_rate || 70) - (a.match_rate || 70));
    
    if (pendingJobs.length === 0) {
        showToast("No pending India jobs found to apply!", true);
        return;
    }
    
    const selectedJobs = pendingJobs.slice(0, 10);
    const jobIds = selectedJobs.map(j => j.id);
    
    showToast(`Launching batch apply for ${selectedJobs.length} India jobs in browser!`);
    
    indiaBatchApplyBtn.disabled = true;
    indiaBatchApplyBtn.innerText = "🚀 Applying Batch...";
    
    try {
        const res = await fetch('/api/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_ids: jobIds })
        });
        
        if (res.ok) {
            showToast("Batch launched! Watch the automation browser tabs process.");
            
            let pollCount = 0;
            const maxPolls = 120; // 6 minutes max safety limit
            
            const pollInterval = setInterval(async () => {
                pollCount++;
                await loadData();
                
                // Check if all batch jobs are processed
                const batchJobs = jobs.filter(j => jobIds.includes(j.id));
                const allProcessed = batchJobs.every(j => j.status && j.status !== 'Pending');
                
                if (allProcessed || pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    indiaBatchApplyBtn.disabled = false;
                    indiaBatchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
                    
                    const appliedCount = batchJobs.filter(j => j.status === 'Applied').length;
                    const reviewCount = batchJobs.filter(j => j.status === 'Review Required').length;
                    
                    showToast(`India Batch Apply finished! Successful: ${appliedCount}, Review needed: ${reviewCount}`);
                }
            }, 3000);
        } else {
            showToast("Failed to launch batch apply.", true);
            indiaBatchApplyBtn.disabled = false;
            indiaBatchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
        }
    } catch (e) {
        showToast("Error connecting to automation backend.", true);
        indiaBatchApplyBtn.disabled = false;
        indiaBatchApplyBtn.innerText = "🚀 Apply Batch (Top 10)";
    }
});

// Quick Apply — paste URLs
quickApplyBtn.addEventListener('click', async () => {
    const raw = document.getElementById('quickApplyUrls').value.trim();
    const urls = raw.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
    if (urls.length === 0) {
        showToast("Please paste at least one valid URL.", true);
        return;
    }
    quickApplyBtn.disabled = true;
    quickApplyBtn.innerText = "Launching...";
    const resultsEl = document.getElementById('quickApplyResults');
    resultsEl.innerHTML = urls.map(u => `<div style="padding:0.6rem;margin:0.4rem 0;background:var(--glass);border-radius:8px;border:1px solid var(--glass-border);font-size:0.85rem;"><span style="color:var(--text-muted);">⏳ Pending</span> — ${escapeHtml(u.slice(0, 80))}</div>`).join('');

    try {
        const res = await fetch('/api/apply-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed');
        showToast(`Launched auto-apply for ${urls.length} URL(s)!`);
        quickApplyBtn.innerText = "Applying in browser...";

        // Poll until all custom jobs are resolved
        const jobIds = data.job_ids;
        let polls = 0;
        const iv = setInterval(async () => {
            polls++;
            await loadData();
            const custom = jobs.filter(j => jobIds.includes(j.id));
            resultsEl.innerHTML = custom.map(j => {
                const icon = j.status === 'Applied' ? '✅' : j.status === 'Review Required' ? '⚠️' : '⏳';
                const color = j.status === 'Applied' ? 'var(--success)' : j.status === 'Review Required' ? 'var(--warning)' : 'var(--text-muted)';
                return `<div style="padding:0.6rem;margin:0.4rem 0;background:var(--glass);border-radius:8px;border:1px solid var(--glass-border);font-size:0.85rem;"><span style="color:${color};">${icon} ${escapeHtml(j.status)}</span> — <b>${escapeHtml(j.title)}</b> @ ${escapeHtml(j.company)}</div>`;
            }).join('');
            const allDone = custom.every(j => j.status !== 'Pending');
            if (allDone || polls >= 80) {
                clearInterval(iv);
                quickApplyBtn.disabled = false;
                quickApplyBtn.innerText = "Auto-Apply to All URLs";
                const applied = custom.filter(j => j.status === 'Applied').length;
                showToast(`Quick Apply done! ${applied}/${urls.length} Applied.`);
            }
        }, 4000);
    } catch (e) {
        showToast("Error: " + e.message, true);
        quickApplyBtn.disabled = false;
        quickApplyBtn.innerText = "Auto-Apply to All URLs";
    }
});

// Parse Resume with AI — shared handler
async function handleParseResume(btn) {
    btn.disabled = true;
    const origText = btn.innerText;
    btn.innerText = "Parsing...";
    const statusEl = document.getElementById('parseResumeStatus');
    if (statusEl) statusEl.innerText = "Reading resume with Gemini...";
    try {
        const res = await fetch('/api/parse-resume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Parse failed');
        // Populate matching form fields
        const form = document.getElementById('profileForm');
        const fieldMap = {
            full_name: 'full_name', email: 'email', phone: 'phone',
            location: 'location', linkedin: 'linkedin', github: 'github',
            portfolio: 'portfolio', resume_path: 'resume_path'
        };
        let filled = 0;
        for (const [key, name] of Object.entries(fieldMap)) {
            if (data[key]) {
                const el = form.querySelector(`[name="${name}"]`);
                if (el && !el.value) { el.value = data[key]; filled++; }
            }
        }
        // Custom responses
        const customMap = {
            graduation_year: 'custom_graduation_year',
            university_name: 'custom_university_name',
            gpa_cgpa: 'custom_gpa_cgpa',
            python_experience: 'custom_python_experience',
        };
        for (const [key, name] of Object.entries(customMap)) {
            if (data[key]) {
                const el = form.querySelector(`[name="${name}"]`);
                if (el && !el.value) { el.value = data[key]; filled++; }
            }
        }
        if (statusEl) statusEl.innerText = `Filled ${filled} fields from resume.`;
        showToast(`AI parsed resume — filled ${filled} profile fields!`);
    } catch (e) {
        if (statusEl) statusEl.innerText = "Error: " + e.message;
        showToast("Resume parse failed: " + e.message, true);
    } finally {
        btn.disabled = false;
        btn.innerText = origText;
    }
}

if (parseResumeBtn) parseResumeBtn.addEventListener('click', () => handleParseResume(parseResumeBtn));
if (parseResumeProfileBtn) parseResumeProfileBtn.addEventListener('click', () => handleParseResume(parseResumeProfileBtn));

// Render custom URL jobs in Quick Apply tab
function renderCustomJobs() {
    const el = document.getElementById('customJobsList');
    if (!el) return;
    const custom = jobs.filter(j => j.source === 'Custom URL').slice(0, 20);
    if (custom.length === 0) {
        el.innerHTML = '<p style="color:var(--text-muted);font-size:0.875rem;">No custom URL applications yet.</p>';
        return;
    }
    el.innerHTML = custom.map(j => {
        const icon = j.status === 'Applied' ? '✅' : j.status === 'Review Required' ? '⚠️' : '⏳';
        return `<div style="padding:0.6rem;margin:0.4rem 0;background:var(--glass);border-radius:8px;border:1px solid var(--glass-border);font-size:0.85rem;">${icon} <b>${escapeHtml(j.title)}</b> @ ${escapeHtml(j.company)} — <span style="color:var(--text-muted);">${escapeHtml(j.status)}</span></div>`;
    }).join('');
}

// Init
window.addEventListener('DOMContentLoaded', () => {
    checkServerStatus();
    loadData();
    
    // Add Event Listeners for Filters
    searchInput.addEventListener('input', filterAndRenderJobs);
    statusFilter.addEventListener('change', filterAndRenderJobs);
    sortControl.addEventListener('change', filterAndRenderJobs);
    
    // Add Event Listeners for India Filters
    indiaSearchInput.addEventListener('input', filterAndRenderIndiaJobs);
    indiaStatusFilter.addEventListener('change', filterAndRenderIndiaJobs);
    indiaSortControl.addEventListener('change', filterAndRenderIndiaJobs);
});
