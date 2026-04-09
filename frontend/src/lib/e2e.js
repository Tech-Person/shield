// End-to-End Encryption utilities using Web Crypto API
// RSA-OAEP 2048 for key exchange, AES-256-GCM for message encryption

const RSA_ALGO = {
  name: 'RSA-OAEP',
  modulusLength: 2048,
  publicExponent: new Uint8Array([1, 0, 1]),
  hash: 'SHA-256'
};

function toBase64(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}

function fromBase64(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

// ── Key Generation ──

export async function generateKeyPair() {
  const keyPair = await window.crypto.subtle.generateKey(
    RSA_ALGO,
    true,
    ['wrapKey', 'unwrapKey']
  );
  return keyPair;
}

export async function exportPublicKeyJWK(publicKey) {
  return await window.crypto.subtle.exportKey('jwk', publicKey);
}

export async function exportPrivateKeyJWK(privateKey) {
  return await window.crypto.subtle.exportKey('jwk', privateKey);
}

export async function importPublicKeyJWK(jwk) {
  return await window.crypto.subtle.importKey(
    'jwk', jwk,
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['wrapKey']
  );
}

export async function importPrivateKeyJWK(jwk) {
  return await window.crypto.subtle.importKey(
    'jwk', jwk,
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    true,
    ['unwrapKey']
  );
}

// ── Message Encryption ──

export async function encryptMessage(plaintext, recipientDeviceKeys) {
  // recipientDeviceKeys: [{device_id, publicKey (CryptoKey)}]
  const aesKey = await window.crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt', 'decrypt']
  );

  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    aesKey,
    encoded
  );

  // Wrap AES key with each recipient device's RSA public key
  const encryptedKeys = {};
  for (const { device_id, publicKey } of recipientDeviceKeys) {
    const wrappedKey = await window.crypto.subtle.wrapKey(
      'raw', aesKey, publicKey, { name: 'RSA-OAEP' }
    );
    encryptedKeys[device_id] = toBase64(wrappedKey);
  }

  return {
    encrypted_content: toBase64(ciphertext),
    iv: toBase64(iv),
    encrypted_keys: encryptedKeys
  };
}

export async function decryptMessage(encryptedContent, ivB64, wrappedKeyB64, privateKey) {
  const wrappedKeyBuf = fromBase64(wrappedKeyB64);
  const ivBuf = fromBase64(ivB64);
  const ciphertextBuf = fromBase64(encryptedContent);

  const aesKey = await window.crypto.subtle.unwrapKey(
    'raw',
    wrappedKeyBuf,
    privateKey,
    { name: 'RSA-OAEP' },
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt']
  );

  const decrypted = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: ivBuf },
    aesKey,
    ciphertextBuf
  );

  return new TextDecoder().decode(decrypted);
}

// ── Key Backup (passphrase-encrypted) ──

async function deriveBackupKey(passphrase, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']
  );
  return await window.crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 600000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

export async function encryptPrivateKeyForBackup(privateKey, passphrase) {
  const jwk = await exportPrivateKeyJWK(privateKey);
  const data = new TextEncoder().encode(JSON.stringify(jwk));
  const salt = window.crypto.getRandomValues(new Uint8Array(16));
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const backupKey = await deriveBackupKey(passphrase, salt);
  const encrypted = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv }, backupKey, data
  );
  return {
    encrypted_private_key: toBase64(encrypted),
    salt: toBase64(salt),
    iv: toBase64(iv)
  };
}

export async function decryptPrivateKeyFromBackup(encryptedB64, saltB64, ivB64, passphrase) {
  const salt = fromBase64(saltB64);
  const iv = fromBase64(ivB64);
  const encrypted = fromBase64(encryptedB64);
  const backupKey = await deriveBackupKey(passphrase, new Uint8Array(salt));
  const decrypted = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: new Uint8Array(iv) }, backupKey, encrypted
  );
  const jwk = JSON.parse(new TextDecoder().decode(decrypted));
  return await importPrivateKeyJWK(jwk);
}

// ── Device ID ──

export function getDeviceId() {
  let id = localStorage.getItem('shield_device_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('shield_device_id', id);
  }
  return id;
}
