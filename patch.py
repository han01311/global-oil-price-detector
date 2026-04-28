import re
with open('frontend/src/components/NewsExplorer/NewsExplorer.css', 'r') as f:
    css = f.read()

old_banner = """/* ── Active Date Banner ── */
.active-date-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.3);
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  animation: slide-up-fade 0.3s ease-out forwards;
}

.active-date-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.active-date-label {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.active-date-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.active-date-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: var(--color-card);
  padding: 2px 6px;
  border-radius: 12px;
}

.clear-date-button {
  background: transparent;
  border: 1px solid var(--color-primary);
  color: var(--color-primary);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.clear-date-button:hover {
  background: var(--color-primary);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
}
.date-badge-close:hover {
  color: #ff6b6b;
}"""

new_chip = """/* ── Active Date Chip ── */
.active-date-chip-container {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.active-date-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background-color: var(--color-card-hover);
  border: 1px solid var(--color-border);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  color: var(--color-text-secondary);
  animation: fade-in 0.2s ease-out;
}

.active-date-chip strong {
  color: var(--color-text-primary);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.active-date-count {
  font-size: 12px;
  color: var(--color-text-muted);
}

.clear-chip-button {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 2px;
  margin-left: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.clear-chip-button:hover {
  background: var(--color-border);
  color: var(--color-text-primary);
}"""

if old_banner in css:
    css = css.replace(old_banner, new_chip)
    with open('frontend/src/components/NewsExplorer/NewsExplorer.css', 'w') as f:
        f.write(css)
    print("Patched!")
else:
    print("Not found!")
