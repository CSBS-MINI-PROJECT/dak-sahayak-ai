'use client';

import { useState } from 'react';
import { calculateTariff } from '../lib/api';

const SCHEMES = [
  { id: 'sukanya', name: 'Sukanya Samriddhi (SSA)', rate: '8.2%', defaultAmt: 10000 },
  { id: 'ppf', name: 'Public Provident Fund (PPF)', rate: '7.1%', defaultAmt: 10000 },
  { id: 'scss', name: 'Senior Citizen Savings (SCSS)', rate: '8.2%', defaultAmt: 100000 },
  { id: 'mis', name: 'Monthly Income Scheme (MIS)', rate: '7.4%', defaultAmt: 100000 },
  { id: 'nsc', name: 'National Savings Cert (NSC)', rate: '7.7%', defaultAmt: 10000 },
  { id: 'kvp', name: 'Kisan Vikas Patra (KVP)', rate: '7.5%', defaultAmt: 10000 }
];

export default function FinancialCalculator({ isOpen, onClose }) {
  const [scheme, setScheme] = useState('sukanya');
  const [amount, setAmount] = useState(10000);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);

  if (!isOpen) return null;

  const handleCalculate = async (e) => {
    e?.preventDefault();
    setLoading(true);
    try {
      const payload = { service: scheme };
      if (scheme === 'sukanya' || scheme === 'ppf') {
        payload.annual_deposit = Number(amount);
      } else {
        payload.deposit_amount = Number(amount);
      }
      const data = await calculateTariff(payload);
      setResult(data);
    } catch (err) {
      console.error('Financial calc error:', err);
    } finally {
      setLoading(false);
    }
  };

  const selectedSchemeObj = SCHEMES.find(s => s.id === scheme);

  const handleDownloadROI = (format = 'pdf') => {
    if (!result) return;
    setShowDownloadMenu(false);
    const schemeTitle = selectedSchemeObj ? selectedSchemeObj.name : scheme.toUpperCase();
    const dateStr = new Date().toLocaleDateString('en-IN');

    if (format === 'doc' || format === 'txt') {
      let text = `INDIA POST - SAVINGS SCHEME ROI ESTIMATE\nScheme: ${schemeTitle}\nDate: ${dateStr}\n\n`;
      text += `Deposit Amount: ₹${Number(amount).toLocaleString('en-IN')}\n`;
      if (result.total_invested !== undefined) text += `Total Amount Invested: ₹${result.total_invested?.toLocaleString('en-IN')}\n`;
      if (result.interest_earned !== undefined) text += `Total Interest Earned: ₹${result.interest_earned?.toLocaleString('en-IN')}\n`;
      if (result.quarterly_payout !== undefined) text += `Quarterly Pension Payout: ₹${result.quarterly_payout?.toLocaleString('en-IN')}\n`;
      if (result.monthly_payout !== undefined) text += `Monthly Income Payout: ₹${result.monthly_payout?.toLocaleString('en-IN')}\n`;
      if (result.maturity_value !== undefined) text += `Final Maturity Value: ₹${result.maturity_value?.toLocaleString('en-IN')}\n`;
      text += `\nNote: Rates and calculations are based on official Department of Posts guidelines.`;

      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `IndiaPost_${scheme}_ROI_${new Date().toISOString().split('T')[0]}.${format === 'doc' ? 'doc' : 'txt'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else {
      const printWindow = window.open('', '_blank');
      if (!printWindow) {
        alert('Please allow popups to save/print the PDF.');
        return;
      }
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <title>ROI Estimate - ${schemeTitle}</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; color: #222; }
            .header { border-bottom: 2px solid #c4122f; padding-bottom: 15px; margin-bottom: 25px; }
            .header h1 { margin: 0; color: #c4122f; font-size: 22px; }
            .header p { margin: 4px 0 0 0; color: #666; font-size: 13px; }
            .scheme-badge { display: inline-block; background: #fff3e0; color: #e65100; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 14px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #eee; font-size: 15px; }
            th { color: #555; background: #fafafa; }
            .highlight { color: #2e7d32; font-weight: 700; font-size: 18px; }
            .footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 12px; color: #888; text-align: center; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>डाक सहायक (Dak Sahayak)</h1>
            <p>Official India Post Small Savings ROI Breakdown</p>
          </div>
          <div class="scheme-badge">${schemeTitle} (${selectedSchemeObj?.rate || ''})</div>
          <table>
            <tr>
              <td><strong>Deposit Amount:</strong></td>
              <td>₹${Number(amount).toLocaleString('en-IN')}</td>
            </tr>
            ${result.total_invested !== undefined ? `
            <tr>
              <td>Total Amount Invested:</td>
              <td>₹${result.total_invested?.toLocaleString('en-IN')}</td>
            </tr>` : ''}
            ${result.interest_earned !== undefined ? `
            <tr>
              <td>Total Interest Earned:</td>
              <td style="color:#f57c00; font-weight:600;">₹${result.interest_earned?.toLocaleString('en-IN')}</td>
            </tr>` : ''}
            ${result.quarterly_payout !== undefined ? `
            <tr>
              <td>Quarterly Pension Payout:</td>
              <td style="color:#2e7d32; font-weight:600;">₹${result.quarterly_payout?.toLocaleString('en-IN')} / quarter</td>
            </tr>` : ''}
            ${result.monthly_payout !== undefined ? `
            <tr>
              <td>Monthly Income Payout:</td>
              <td style="color:#2e7d32; font-weight:600;">₹${result.monthly_payout?.toLocaleString('en-IN')} / month</td>
            </tr>` : ''}
            ${result.maturity_value !== undefined ? `
            <tr style="background:#f1f8e9;">
              <td><strong>Final Maturity Value:</strong></td>
              <td class="highlight">₹${result.maturity_value?.toLocaleString('en-IN')}</td>
            </tr>` : ''}
          </table>
          <div class="footer">
            Generated on ${dateStr} • Department of Posts, Government of India
          </div>
          <script>
            window.onload = function() { window.print(); };
          </script>
        </body>
        </html>
      `;
      printWindow.document.open();
      printWindow.document.write(html);
      printWindow.document.close();
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <i className="fa-solid fa-coins" style={{ color: 'var(--accent-gold)' }}></i>
            <span>Post Office Small Savings ROI Calculator</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleCalculate}>
            <div className="form-group">
              <label>Select Small Savings Scheme</label>
              <select
                className="form-control"
                value={scheme}
                onChange={(e) => {
                  setScheme(e.target.value);
                  const found = SCHEMES.find(s => s.id === e.target.value);
                  if (found) setAmount(found.defaultAmt);
                  setResult(null);
                }}
              >
                {SCHEMES.map(s => (
                  <option key={s.id} value={s.id}>{s.name} ({s.rate})</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>
                {scheme === 'sukanya' || scheme === 'ppf' ? 'Annual Deposit Amount (₹)' : 'One-time Investment Deposit (₹)'}
              </label>
              <input
                type="number"
                min="500"
                max="3000000"
                step="500"
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                className="form-control"
                required
              />
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin"></i> Calculating Maturity...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-calculator"></i> Calculate Maturity &amp; Payout
                </>
              )}
            </button>
          </form>

          {result && (
            <div style={{ marginTop: '20px', padding: '16px', backgroundColor: '#161718', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ color: 'var(--text-bright)', marginBottom: '12px', fontSize: '0.95rem' }}>
                <i className="fa-solid fa-chart-line" style={{ color: 'var(--accent-gold)' }}></i> Estimated Payout Breakdown
              </h4>

              {result.total_invested !== undefined && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Total Amount Invested:</span>
                  <strong>₹{result.total_invested?.toLocaleString('en-IN')}</strong>
                </div>
              )}

              {result.interest_earned !== undefined && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Total Interest Earned:</span>
                  <strong style={{ color: 'var(--accent-gold)' }}>₹{result.interest_earned?.toLocaleString('en-IN')}</strong>
                </div>
              )}

              {result.quarterly_payout !== undefined && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Quarterly Pension Payout:</span>
                  <strong style={{ color: '#81c784' }}>₹{result.quarterly_payout?.toLocaleString('en-IN')} / quarter</strong>
                </div>
              )}

              {result.monthly_payout !== undefined && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Monthly Income Payout:</span>
                  <strong style={{ color: '#81c784' }}>₹{result.monthly_payout?.toLocaleString('en-IN')} / month</strong>
                </div>
              )}

              {result.maturity_value !== undefined && (
                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '1rem', color: '#81c784', fontWeight: 700 }}>
                  <span>Final Maturity Value:</span>
                  <span>₹{result.maturity_value?.toLocaleString('en-IN')}</span>
                </div>
              )}

              {/* Single Download Button with Format Dropdown */}
              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '12px', position: 'relative' }}>
                <button
                  type="button"
                  className="bubble-action-btn"
                  title="Download breakdown"
                  onClick={() => setShowDownloadMenu(prev => !prev)}
                >
                  <i className="fa-solid fa-download" style={{ color: '#ef5350' }}></i>
                  <span>Download</span>
                  <i className="fa-solid fa-chevron-down" style={{ fontSize: '0.65rem', marginLeft: '4px', opacity: 0.7 }}></i>
                </button>

                {showDownloadMenu && (
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '110%',
                      right: 0,
                      background: '#1e2022',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: '10px',
                      overflow: 'hidden',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                      minWidth: '160px',
                      zIndex: 100,
                    }}
                  >
                    {[
                      { format: 'pdf', label: 'PDF (Print)', icon: 'fa-file-pdf', color: '#ef5350' },
                      { format: 'doc', label: 'Word Doc (.doc)', icon: 'fa-file-word', color: '#42a5f5' },
                      { format: 'txt', label: 'Plain Text (.txt)', icon: 'fa-file-lines', color: '#66bb6a' },
                    ].map(({ format, label, icon, color }) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => handleDownloadROI(format)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          width: '100%',
                          padding: '10px 14px',
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--text-bright)',
                          cursor: 'pointer',
                          fontSize: '0.85rem',
                          textAlign: 'left',
                          transition: 'background 0.15s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <i className={`fa-solid ${icon}`} style={{ color, width: '14px' }}></i>
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
