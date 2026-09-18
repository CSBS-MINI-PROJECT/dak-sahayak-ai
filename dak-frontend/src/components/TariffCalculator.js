'use client';

import { useState } from 'react';
import { calculateTariff } from '../lib/api';

export default function TariffCalculator({ isOpen, onClose }) {
  const [weight, setWeight] = useState(250);
  const [distance, setDistance] = useState('up_to_200');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleCalculate = async (e) => {
    e?.preventDefault();
    setLoading(true);
    try {
      const data = await calculateTariff({
        service: 'speed_post',
        weight: Number(weight),
        distance
      });
      setResult(data);
    } catch (err) {
      console.error('Tariff calc error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <i className="fa-solid fa-calculator" style={{ color: 'var(--accent-red)' }}></i>
            <span>Domestic Speed Post Tariff</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleCalculate}>
            <div className="form-group">
              <label>Weight: <strong>{weight} grams</strong></label>
              <input
                type="range"
                min="10"
                max="5000"
                step="10"
                value={weight}
                onChange={(e) => setWeight(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-red)' }}
              />
              <input
                type="number"
                min="1"
                max="35000"
                value={weight}
                onChange={(e) => setWeight(Number(e.target.value))}
                className="form-control"
                style={{ marginTop: '8px' }}
              />
            </div>

            <div className="form-group">
              <label>Distance Slab</label>
              <select
                className="form-control"
                value={distance}
                onChange={(e) => setDistance(e.target.value)}
              >
                <option value="local">Local (Intra-city)</option>
                <option value="up_to_200">Up to 200 km</option>
                <option value="201_to_1000">201 to 1000 km</option>
                <option value="1001_to_2000">1001 to 2000 km</option>
                <option value="above_2000">Above 2000 km</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin"></i> Calculating...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-coins"></i> Calculate Charges
                </>
              )}
            </button>
          </form>

          {result && (
            <div style={{ marginTop: '20px', padding: '16px', backgroundColor: 'var(--card-inner-bg)', borderRadius: '12px', border: '1px solid var(--card-inner-border)' }}>
              <h4 style={{ color: 'var(--text-bright)', marginBottom: '12px', fontSize: '0.95rem' }}>
                <i className="fa-solid fa-receipt" style={{ color: 'var(--accent-gold)' }}></i> Official Tariff Breakdown
              </h4>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Weight Slab:</span>
                <strong>{result.weight_slab || `${weight}g`}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Distance Slab:</span>
                <strong>{result.distance_slab || distance}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Base Tariff:</span>
                <strong>₹{result.base_tariff?.toFixed(2) || '0.00'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>GST (18%):</span>
                <strong>₹{result.gst?.toFixed(2) || '0.00'}</strong>
              </div>
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '1rem', color: '#81c784', fontWeight: 700 }}>
                <span>Total Payable:</span>
                <span>₹{result.total_payable?.toFixed(2) || '0.00'}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
