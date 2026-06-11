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

// Stats Elements
const statTotalEl = document.getElementById('statTotal');
const statAppliedEl = document.getElementById('statApplied');
const statPendingEl = document.getElementById('statPending');
const statMatchEl = document.getElementById('statMatch');

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
        const response = await fetch('/jobs_database.json');
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
        const jobsRes = await fetch('/jobs_database.json');
        if (jobsRes.ok) {
            jobs = await jobsRes.json();
            renderStats();
            filterAndRenderJobs();
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
}

// Render Stats Card
function renderStats() {
    if (!jobs.length) return;
    
    const total = jobs.length;
    const applied = jobs.filter(j => j.status === 'Applied').length;
    const pending = jobs.filter(j => j.status === 'Pending' || !j.status).length;
    
    const sumMatch = jobs.reduce((sum, j) => sum + (j.match_rate || 70), 0);
    const avgMatch = Math.round(sumMatch / total);
    
    statTotalEl.innerText = total;
    statAppliedEl.innerText = applied;
    statPendingEl.innerText = pending;
    statMatchEl.innerText = `${avgMatch}%`;
}

// Filter and Render Jobs List
function filterAndRenderJobs() {
    const searchTerm = searchInput.value.toLowerCase();
    const selectedStatus = statusFilter.value;
    const sortBy = sortControl.value;
    
    let filtered = jobs.filter(job => {
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
            <h2>${job.title}</h2>
            <div class="company">${job.company}</div>
            <div class="meta-row">
                <span>📍 ${job.location}</span>
                <span>📅 Posted: ${job.date_posted || 'June 2026'}</span>
                <span>ℹ️ Source: ${job.source || 'Portal'}</span>
            </div>
        </div>
        
        <div class="detail-body">
            <div class="detail-section">
                <h4>Match Quality Analysis</h4>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent-cyan); margin-bottom: 0.25rem;">
                    ${job.match_rate || 70}% Match
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
                <p>${job.description}</p>
            </div>
            
            <div class="actions-section">
                <button id="applyBtn" class="${applyButtonClass}" style="width: 100%; font-size: 1rem; padding: 0.9rem;">
                    ${applyButtonText}
                </button>
                <a href="${job.url}" target="_blank" class="btn btn-secondary" style="width: 100%;">
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
    
    // In a real application, we would write back to file. We can update memory and save.
    // We can save by calling save profile or save jobs. Since we don't have a direct save-jobs endpoint,
    // we can implement save-jobs in server or just keep local state. But wait, we can also use our Playwright script
    // which updates it, or we can just send it. Let's make an API call to save jobs if we want.
    // Actually, we can update the jobs in memory and show stats.
    renderStats();
    filterAndRenderJobs();
    if (selectedJobId === jobId) {
        selectJob(jobId);
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

// Init
window.addEventListener('DOMContentLoaded', () => {
    checkServerStatus();
    loadData();
    
    // Add Event Listeners for Filters
    searchInput.addEventListener('input', filterAndRenderJobs);
    statusFilter.addEventListener('change', filterAndRenderJobs);
    sortControl.addEventListener('change', filterAndRenderJobs);
});
