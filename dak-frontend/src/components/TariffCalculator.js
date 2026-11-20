'use client';

import { useState } from 'react';
import { calculateTariff } from '../lib/api';

const SERVICES = [
  { id: 'speed_post', label: 'Speed Post (Domestic)', icon: 'fa-truck-fast' },
  { id: 'letter', label: 'Letters (₹5 / 20g)', icon: 'fa-envelope' },
  { id: 'inland_letter', label: 'Letter Card (Inland ₹2.50)', icon: 'fa-file-lines' },
  { id: 'postcard', label: 'Postcard (Single / Printed)', icon: 'fa-id-card' },
  { id: 'book_post', label: 'Book Post / Printed Books', icon: 'fa-book-open' },
  { id: 'gyan_post', label: 'Gyan Post', icon: 'fa-graduation-cap' },
  { id: 'periodical', label: 'Periodical Post', icon: 'fa-newspaper' },
  { id: 'newspaper', label: 'Registered Newspaper', icon: 'fa-paper-plane' },
  { id: 'parcel', label: 'Ordinary Parcel (₹19/500g)', icon: 'fa-box' },
  { id: 'registered', label: 'Registered Post', icon: 'fa-shield-halved' },
  { id: 'blind', label: 'Literature for the Blind (Free)', icon: 'fa-braille' }
];

export default function TariffCalculator({ isOpen, onClose }) {
  const [service, setService] = useState('speed_post');
  const [weight, setWeight] = useState(250);
  const [fromPincode, setFromPincode] = useState('560001');
  const [toPincode, setToPincode] = useState('110001');
  const [cardType, setCardType] = useState('single');
  const [isPrintedBooks, setIsPrintedBooks] = useState(false);
  const [valueTier, setValueTier] = useState('tier1');
  const [isMultipleCopies, setIsMultipleCopies] = useState(false);
  const [postage, setPostage] = useState(5.0);
  const [adCard, setAdCard] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSwapPincodes = () => {
    const temp = fromPincode;
    setFromPincode(toPincode);
    setToPincode(temp);
    setResult(null);
  };

  const handleCalculate = async (e) => {
    e?.preventDefault();
    setLoading(true);
    try {
      const data = await calculateTariff({
        service,
        weight: Number(weight),
        from_pincode: fromPincode.trim(),
        to_pincode: toPincode.trim(),
        card_type: cardType,
        is_printed_books: isPrintedBooks,
        value_tier: valueTier,
        is_multiple_copies: isMultipleCopies,
        postage: Number(postage),
        ad_card: adCard
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
      <div className="modal-card w-full max-w-[95vw] md:max-w-xl mx-2 rounded-2xl max-h-[90dvh] overflow-y-auto overflow-x-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <i className="fa-solid fa-calculator" style={{ color: 'var(--accent-red)' }}></i>
            <span>India Post Domestic Tariff Calculator</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleCalculate}>
            {/* Service Selector */}
            <div className="form-group">
              <label>Select Postal Service</label>
              <select
                className="form-control"
                value={service}
                onChange={(e) => {
                  setService(e.target.value);
                  setResult(null);
                }}
              >
                {SERVICES.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </div>

            {/* PIN Code Route (From & To) */}
            <div className="form-group">
              <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Route (From PIN & To PIN)</span>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Distance calculated automatically
                </span>
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-2 items-end">
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    <i className="fa-solid fa-location-dot" style={{ color: '#4caf50', marginRight: '4px' }}></i>
                    From PIN Code (Origin)
                  </div>
                  <input
                    type="text"
                    maxLength={6}
                    placeholder="e.g. 560001"
                    value={fromPincode}
                    onChange={(e) => {
                      setFromPincode(e.target.value.replace(/\D/g, ''));
                      setResult(null);
                    }}
                    className="form-control"
                    required
                  />
                </div>

                <button
                  type="button"
                  onClick={handleSwapPincodes}
                  title="Swap From and To PIN codes"
                  className="self-center sm:self-end mb-1 h-10 w-10 flex items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--card-inner-bg)] hover:border-[var(--accent-red)] transition-colors mx-auto"
                >
                  <i className="fa-solid fa-right-left rotate-90 sm:rotate-0"></i>
                </button>

                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    <i className="fa-solid fa-map-pin" style={{ color: 'var(--accent-red)', marginRight: '4px' }}></i>
                    To PIN Code (Destination)
                  </div>
                  <input
                    type="text"
                    maxLength={6}
                    placeholder="e.g. 110001"
                    value={toPincode}
                    onChange={(e) => {
                      setToPincode(e.target.value.replace(/\D/g, ''));
                      setResult(null);
                    }}
                    className="form-control"
                    required
                  />
                </div>
              </div>
            </div>

            {/* Weight inputs for weight-based services */}
            {!['inland_letter', 'postcard', 'blind'].includes(service) && (
              <div className="form-group">
                <label>Item Weight: <strong>{weight} grams</strong></label>
                <input
                  type="range"
                  min="5"
                  max={service === 'letter' ? 2000 : service === 'book_post' ? 5000 : 35000}
                  step="5"
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
            )}

            {/* Postcard Type */}
            {service === 'postcard' && (
              <div className="form-group">
                <label>Postcard Type</label>
                <select
                  className="form-control"
                  value={cardType}
                  onChange={(e) => setCardType(e.target.value)}
                >
                  <option value="single">Single Postcard (50 paise)</option>
                  <option value="reply">Reply Postcard (₹1.00)</option>
                  <option value="printed">Printed Postcard (₹6.00)</option>
                  <option value="competition">Competition Postcard (₹10.00)</option>
                  <option value="meghdoot">Meghdoot Postcard (25 paise)</option>
                </select>
              </div>
            )}

            {/* Book Post Category */}
            {service === 'book_post' && (
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="printedBooks"
                  checked={isPrintedBooks}
                  onChange={(e) => setIsPrintedBooks(e.target.checked)}
                />
                <label htmlFor="printedBooks" style={{ margin: 0, cursor: 'pointer' }}>
                  Contains Printed Books only (Special lower rate: ₹1/100g)
                </label>
              </div>
            )}

            {/* Periodicals Tier */}
            {service === 'periodical' && (
              <div className="form-group">
                <label>Printed Periodical Declared Value</label>
                <select
                  className="form-control"
                  value={valueTier}
                  onChange={(e) => setValueTier(e.target.value)}
                >
                  <option value="tier1">Value between ₹1 to ₹20</option>
                  <option value="tier2">Value between ₹21 to ₹50</option>
                  <option value="tier3">Value ₹51 and above</option>
                </select>
              </div>
            )}

            {/* Registered Newspaper */}
            {service === 'newspaper' && (
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="multiCopies"
                  checked={isMultipleCopies}
                  onChange={(e) => setIsMultipleCopies(e.target.checked)}
                />
                <label htmlFor="multiCopies" style={{ margin: 0, cursor: 'pointer' }}>
                  Packet contains multiple copies of the same issue
                </label>
              </div>
            )}

            {/* Registered Post Options */}
            {service === 'registered' && (
              <>
                <div className="form-group">
                  <label>Base Letter/Packet Postage (₹)</label>
                  <input
                    type="number"
                    min="1"
                    step="0.5"
                    value={postage}
                    onChange={(e) => setPostage(Number(e.target.value))}
                    className="form-control"
                  />
                </div>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    id="adCard"
                    checked={adCard}
                    onChange={(e) => setAdCard(e.target.checked)}
                  />
                  <label htmlFor="adCard" style={{ margin: 0, cursor: 'pointer' }}>
                    Include Acknowledgement Due (AD) Card (+₹3.00)
                  </label>
                </div>
              </>
            )}

            <button type="submit" className="btn-primary" disabled={loading || fromPincode.length !== 6 || toPincode.length !== 6} style={{ marginTop: '8px' }}>
              {loading ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin"></i> Calculating Distance & Tariff...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-coins"></i> Calculate Official Tariff
                </>
              )}
            </button>
          </form>

          {result && (
            <div style={{ marginTop: '20px', padding: '16px', backgroundColor: 'var(--card-inner-bg)', borderRadius: '12px', border: '1px solid var(--card-inner-border)' }}>
              <h4 style={{ color: 'var(--text-bright)', marginBottom: '12px', fontSize: '0.95rem' }}>
                <i className="fa-solid fa-receipt" style={{ color: 'var(--accent-gold)' }}></i> Official Tariff Breakdown
              </h4>

              {/* Calculated Route Details */}
              {result.distance_km !== undefined && (
                <div style={{ marginBottom: '12px', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Postal Route:</span>
                    <span style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--accent-gold)' }}>
                      <i className="fa-solid fa-route" style={{ marginRight: '5px' }}></i>
                      {result.distance_km} km
                    </span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-bright)', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div>
                      <i className="fa-solid fa-circle-dot" style={{ color: '#4caf50', fontSize: '0.7rem', marginRight: '6px' }}></i>
                      <strong>Origin:</strong> {result.from_location || `PIN ${result.from_pincode}`}
                    </div>
                    <div>
                      <i className="fa-solid fa-location-dot" style={{ color: 'var(--accent-red)', fontSize: '0.7rem', marginRight: '6px' }}></i>
                      <strong>Destination:</strong> {result.to_location || `PIN ${result.to_pincode}`}
                    </div>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Service:</span>
                <strong>{result.service || service}</strong>
              </div>

              {result.distance_label && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Distance Slab:</span>
                  <strong style={{ color: 'var(--accent-gold)' }}>{result.distance_label}</strong>
                </div>
              )}

              {result.weight_slab && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Weight Slab:</span>
                  <span>{result.weight_slab}</span>
                </div>
              )}

              {result.rate_description && !result.rate_description.startsWith('Calculated Route:') && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Rate Slab:</span>
                  <span style={{ textAlign: 'right', fontWeight: 600 }}>{result.rate_description}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.88rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Base Postage / Tariff:</span>
                <strong>₹{result.base_tariff !== undefined ? Number(result.base_tariff).toFixed(2) : '0.00'}</strong>
              </div>

              {Number(result.gst_amount || 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.88rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>GST ({result.gst_rate || '18%'}):</span>
                  <strong>₹{Number(result.gst_amount).toFixed(2)}</strong>
                </div>
              )}

              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '1.05rem', color: '#81c784', fontWeight: 700 }}>
                <span>Total Payable:</span>
                <span>₹{Number(result.total_payable || 0).toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
