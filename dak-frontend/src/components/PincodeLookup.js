'use client';

import { useState } from 'react';
import { searchPincode } from '../lib/api';

export default function PincodeLookup({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  if (!isOpen) return null;

  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await searchPincode(query.trim());
      setResults(data.results || []);
    } catch (err) {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card w-full max-w-[95vw] md:max-w-2xl mx-2 rounded-2xl max-h-[90dvh] overflow-y-auto overflow-x-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <i className="fa-solid fa-location-dot" style={{ color: 'var(--accent-red)' }}></i>
            <span>India Post PIN Directory Search</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Enter 6-digit PIN or Post Office (e.g. 575001 or Connaught Place)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <button type="submit" className="btn-primary" disabled={loading} style={{ width: 'auto', padding: '0 20px' }}>
              {loading ? <i className="fa-solid fa-spinner fa-spin"></i> : <i className="fa-solid fa-magnifying-glass"></i>}
            </button>
          </form>

          {loading && (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
              <i className="fa-solid fa-spinner fa-spin"></i> Searching master PIN directory...
            </p>
          )}

          {!loading && searched && results.length === 0 && (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
              No post office records found for "{query}".
            </p>
          )}

          {!loading && results.length > 0 && (
            <div className="overflow-x-auto w-full max-w-full block" style={{ maxHeight: '350px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', textAlign: 'left' }}>
                    <th style={{ padding: '8px' }}>PIN</th>
                    <th style={{ padding: '8px' }}>Office Name</th>
                    <th style={{ padding: '8px' }}>Type</th>
                    <th style={{ padding: '8px' }}>District / State</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((po, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '8px', fontWeight: 600, color: 'var(--accent-gold)' }}>{po.Pincode}</td>
                      <td style={{ padding: '8px', color: 'var(--text-bright)' }}>{po.Name}</td>
                      <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{po.BranchType}</td>
                      <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{po.District}, {po.State}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
