import { supabase } from './supabase';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000/api';

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { 'Authorization': `Bearer ${session.access_token}` };
  }
  return {};
}

export async function fetchConversations() {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_BASE}/conversations`, {
    headers: { ...authHeader, 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error('Failed to fetch conversations');
  const data = await res.json();
  return data.conversations || [];
}

export async function createConversation(title = 'New Chat') {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { ...authHeader, 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return await res.json();
}

export async function deleteConversation(conversationId) {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: { ...authHeader }
  });
  if (!res.ok) throw new Error('Failed to delete conversation');
  return await res.json();
}

export async function fetchMessages(conversationId) {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    headers: { ...authHeader, 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error('Failed to fetch messages');
  const data = await res.json();
  return data.messages || [];
}

export async function sendChatMessageStream({ message, conversationId, language, onChunk, onDone, onError }) {
  const authHeader = await getAuthHeader();
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        language
      })
    });

    if (!res.ok) {
      throw new Error(`Server returned status ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulated = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      accumulated += chunk;
      if (onChunk) onChunk(chunk, accumulated);
    }

    if (onDone) onDone(accumulated);
  } catch (err) {
    if (onError) onError(err);
  }
}

export async function calculateTariff(payload) {
  const res = await fetch(`${API_BASE}/calculator`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to calculate tariff');
  return await res.json();
}

export async function searchPincode(query) {
  const trimmed = String(query || '').trim();

  // When a user searches a 6-digit PIN code, fetch live data from postalpincode API
  if (/^\d{6}$/.test(trimmed)) {
    try {
      const res = await fetch(`https://api.postalpincode.in/pincode/${trimmed}`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data[0]?.Status === 'Success' && Array.isArray(data[0]?.PostOffice)) {
          return {
            status: 'Success',
            results: data[0].PostOffice.map((po) => ({
              Pincode: po.Pincode || trimmed,
              Name: po.Name,
              BranchType: po.BranchType,
              DeliveryStatus: po.DeliveryStatus,
              District: po.District,
              State: po.State,
              Circle: po.Circle,
              Division: po.Division,
              Region: po.Region,
              Block: po.Block
            }))
          };
        }
      }
    } catch (err) {
      console.warn('Direct postalpincode API fetch error, trying backend fallback:', err);
    }
  }

  const res = await fetch(`${API_BASE}/pincode/${encodeURIComponent(trimmed)}`);
  if (!res.ok) throw new Error('Pincode not found');
  return await res.json();
}

export async function reversePincode(lat, lon) {
  const res = await fetch(`${API_BASE}/reverse-pincode?lat=${lat}&lon=${lon}`);
  if (!res.ok) throw new Error('Failed to reverse geocode location');
  return await res.json();
}

export async function fetchTTSAudio(text, language = 'English', gender = 'female') {
  const res = await fetch(`${API_BASE}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language, gender })
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || `TTS request failed with status ${res.status}`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function translateToEnglish(text, sourceLanguage = 'auto') {
  const res = await fetch(`${API_BASE}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, source_language: sourceLanguage })
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || `Translation failed with status ${res.status}`);
  }

  const data = await res.json();
  return data.translated_text;
}
