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
                  <i className="fa-solid fa-calculator"></i> Calculate Maturity & Payout
                </>
              )}
            </button>
          </form>

          {result && (
            <div style={{ marginTop: '20px', padding: '16px', backgroundColor: 'var(--card-inner-bg)', borderRadius: '12px', border: '1px solid var(--card-inner-border)' }}>
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
