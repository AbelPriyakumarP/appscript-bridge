/**
 * AppScript Bridge — Universal Handler
 * Uses Gmail REST API directly via UrlFetchApp to avoid MailApp/GmailApp
 * authorization issues when called through the Execution API.
 */

// ─────────────────────────────────────────────────────────────────────────────
//  UNIVERSAL DISPATCHER
// ─────────────────────────────────────────────────────────────────────────────

function handleEvent(params) {
  params = params || {};
  try {
    var action = params.action || 'sendEmail';
    switch (action) {
      case 'sendEmail':        return sendEmail(params);
      case 'sendGChatMessage': return sendGChatMessage(params);
      case 'sendGChatCard':    return sendGChatCard(params);
      case 'sendGChatDM':      return sendGChatDM(params);
      case 'logToSheet':       return logToSheet(params);
      case 'createDoc':        return createDoc(params);
      default:
        return { success: false, error: 'Unknown action: ' + action };
    }
  } catch (e) {
    Logger.log('handleEvent error: ' + e.message);
    return { success: false, error: e.message };
  }
}


// ─────────────────────────────────────────────────────────────────────────────
//  1. SEND EMAIL  (Gmail REST API → no MailApp/GmailApp auth issues)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Send an email using the Gmail REST API directly via UrlFetchApp.
 * This is the most reliable method when called via the Execution API.
 *
 * params:
 *   recipient  — to address (required)
 *   subject    — subject line
 *   body       — plain-text body
 *   htmlBody   — (optional) HTML body
 *   cc         — (optional) CC
 *   bcc        — (optional) BCC
 */
function sendEmail(params) {
  params = params || {};

  var to = params.recipient || params.to || params.email || '';
  if (!to) {
    return {
      success: false,
      error: 'sendEmail: "recipient" is missing. Add a parameter mapping in AppScript Bridge: name=recipient, value=your@email.com'
    };
  }

  var subject  = params.subject  || '[AppScript Bridge] Notification';
  var bodyText = params.body     || JSON.stringify(params, null, 2);
  var htmlBody = params.htmlBody || null;

  // Build RFC 2822 message
  var lines = [];
  lines.push('To: ' + to);
  if (params.cc)  lines.push('Cc: ' + params.cc);
  if (params.bcc) lines.push('Bcc: ' + params.bcc);
  lines.push('Subject: ' + subject);
  lines.push('MIME-Version: 1.0');

  if (htmlBody) {
    var boundary = 'boundary_' + new Date().getTime();
    lines.push('Content-Type: multipart/alternative; boundary="' + boundary + '"');
    lines.push('');
    lines.push('--' + boundary);
    lines.push('Content-Type: text/plain; charset=UTF-8');
    lines.push('');
    lines.push(bodyText);
    lines.push('--' + boundary);
    lines.push('Content-Type: text/html; charset=UTF-8');
    lines.push('');
    lines.push(htmlBody);
    lines.push('--' + boundary + '--');
  } else {
    lines.push('Content-Type: text/plain; charset=UTF-8');
    lines.push('');
    lines.push(bodyText);
  }

  var raw = Utilities.base64EncodeWebSafe(lines.join('\r\n'));

  // Try Gmail REST API first (most reliable)
  var token = ScriptApp.getOAuthToken();
  try {
    var resp = UrlFetchApp.fetch(
      'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
      {
        method:             'post',
        contentType:        'application/json',
        headers:            { Authorization: 'Bearer ' + token },
        payload:            JSON.stringify({ raw: raw }),
        muteHttpExceptions: true
      }
    );

    var code = resp.getResponseCode();
    if (code === 200) {
      Logger.log('sendEmail OK (Gmail API) → ' + to);
      return { success: true, action: 'sendEmail', method: 'GmailAPI', to: to, subject: subject };
    }

    // 401/403 means the token doesn't have mail scope yet → fall through to GmailApp
    Logger.log('Gmail API returned ' + code + ': ' + resp.getContentText());
  } catch (apiErr) {
    Logger.log('Gmail API fetch error: ' + apiErr.message);
  }

  // Fallback 1: GmailApp
  try {
    var opts = {};
    if (params.cc)       opts.cc       = params.cc;
    if (params.bcc)      opts.bcc      = params.bcc;
    if (htmlBody)        opts.htmlBody = htmlBody;
    GmailApp.sendEmail(to, subject, bodyText, opts);
    Logger.log('sendEmail OK (GmailApp) → ' + to);
    return { success: true, action: 'sendEmail', method: 'GmailApp', to: to, subject: subject };
  } catch (gmailErr) {
    Logger.log('GmailApp error: ' + gmailErr.message);
  }

  // Fallback 2: MailApp
  try {
    MailApp.sendEmail(to, subject, bodyText);
    Logger.log('sendEmail OK (MailApp) → ' + to);
    return { success: true, action: 'sendEmail', method: 'MailApp', to: to, subject: subject };
  } catch (mailErr) {
    Logger.log('MailApp error: ' + mailErr.message);
    return {
      success: false,
      error:   'All email methods failed. Run testAuthorization() once in the Apps Script editor to grant permissions.',
      detail:  mailErr.message
    };
  }
}


/**
 * STEP 1 — Run this FIRST to clear the old cached authorization.
 * In the Apps Script editor: select forceReAuth → click Run.
 * This invalidates the old token and forces a fresh permission prompt.
 */
function forceReAuth() {
  ScriptApp.invalidateAuth();
  Logger.log('Old authorization cleared. Now run testAuthorization() to re-grant all scopes.');
}

/**
 * STEP 2 — Run this AFTER forceReAuth().
 * Select testAuthorization → click Run → click "Review Permissions" → Allow.
 * This grants all scopes including https://mail.google.com/ for email.
 */
function testAuthorization() {
  var token = ScriptApp.getOAuthToken();
  Logger.log('OAuth token: ' + (token ? 'YES — scopes granted' : 'NO — auth failed'));

  try {
    var resp    = UrlFetchApp.fetch(
      'https://gmail.googleapis.com/gmail/v1/users/me/profile',
      { headers: { Authorization: 'Bearer ' + token }, muteHttpExceptions: true }
    );
    var code    = resp.getResponseCode();
    var profile = JSON.parse(resp.getContentText());
    if (code === 200) {
      Logger.log('Gmail access confirmed: ' + profile.emailAddress);
    } else {
      Logger.log('Gmail API returned ' + code + ' — re-run forceReAuth() and try again');
    }
  } catch (e) {
    Logger.log('Gmail test error: ' + e.message);
  }

  Logger.log('Done. If Gmail access is confirmed above, email will work from AppScript Bridge.');
  return { success: true };
}

/**
 * STEP 3 — Send a test email to verify everything works end-to-end.
 * Change the "to" address below then Run this function.
 */
function testSendEmail() {
  var result = sendEmail({
    recipient: 'smahendru@astreya.com',
    subject:   'Test from AppScript Bridge',
    body:      'If you received this, email is working correctly!'
  });
  Logger.log(JSON.stringify(result));
  return result;
}


// ─────────────────────────────────────────────────────────────────────────────
//  2. GOOGLE CHAT — Text message to a Space
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Post a plain-text message to a Google Chat Space.
 *
 * params:
 *   spaceId  — "spaces/XXXXXXXXX" or full Chat URL
 *   message  — text to post
 *   threadKey — (optional) reply to a thread
 */
function sendGChatMessage(params) {
  params = params || {};
  var spaceId = _resolveSpaceId(params.spaceId || params.space || params.chatSpace);
  if (!spaceId) {
    return { success: false, error: 'sendGChatMessage: spaceId is required (e.g. spaces/XXXXXXXXX)' };
  }

  var text    = params.message || params.text || JSON.stringify(params, null, 2);
  var payload = { text: text };
  if (params.threadKey) payload.thread = { threadKey: params.threadKey };

  var resp = _chatApiPost('https://chat.googleapis.com/v1/' + spaceId + '/messages', payload);
  Logger.log('sendGChatMessage → ' + spaceId);
  return { success: true, action: 'sendGChatMessage', space: spaceId };
}


// ─────────────────────────────────────────────────────────────────────────────
//  3. GOOGLE CHAT — Rich Card
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Post a rich card to Google Chat.
 *
 * params:
 *   spaceId      — Chat space name
 *   title        — card title
 *   subtitle     — card subtitle
 *   body         — main text paragraph
 *   buttonLabel  — (optional) action button text
 *   buttonUrl    — (optional) action button URL
 *   field1Label / field1Value ... field10Label / field10Value
 *   threadKey    — (optional)
 */
function sendGChatCard(params) {
  params = params || {};
  var spaceId = _resolveSpaceId(params.spaceId || params.space || params.chatSpace);
  if (!spaceId) {
    return { success: false, error: 'sendGChatCard: spaceId is required' };
  }

  var sections = [];
  if (params.body) {
    sections.push({ widgets: [{ textParagraph: { text: params.body } }] });
  }

  var kvWidgets = _buildKVWidgets(params);
  if (kvWidgets.length > 0) sections.push({ widgets: kvWidgets });

  if (params.buttonLabel && params.buttonUrl) {
    sections.push({
      widgets: [{
        buttons: [{
          textButton: {
            text: params.buttonLabel,
            onClick: { openLink: { url: params.buttonUrl } }
          }
        }]
      }]
    });
  }

  var card = {
    header: {
      title:      params.title    || 'AppScript Bridge',
      subtitle:   params.subtitle || '',
      imageUrl:   'https://www.gstatic.com/images/branding/product/1x/apps_script_48dp.png',
      imageStyle: 'IMAGE'
    },
    sections: sections
  };

  var msgPayload = { cards: [card] };
  if (params.threadKey) msgPayload.thread = { threadKey: params.threadKey };

  _chatApiPost('https://chat.googleapis.com/v1/' + spaceId + '/messages', msgPayload);
  Logger.log('sendGChatCard → ' + spaceId);
  return { success: true, action: 'sendGChatCard', space: spaceId, title: params.title };
}


// ─────────────────────────────────────────────────────────────────────────────
//  4. GOOGLE CHAT — Direct Message
// ─────────────────────────────────────────────────────────────────────────────

function sendGChatDM(params) {
  params = params || {};
  if (!params.userEmail) {
    return { success: false, error: 'sendGChatDM: userEmail is required' };
  }
  try {
    var spaceResp = _chatApiGet(
      'https://chat.googleapis.com/v1/spaces:findDirectMessage?name=users/' + params.userEmail
    );
    var spaceId = spaceResp && spaceResp.name ? spaceResp.name : null;
    if (!spaceId) {
      return { success: false, error: 'sendGChatDM: could not find DM space for ' + params.userEmail };
    }
    var text = params.message || params.text || 'Notification from AppScript Bridge';
    _chatApiPost('https://chat.googleapis.com/v1/' + spaceId + '/messages', { text: text });
    Logger.log('sendGChatDM → ' + params.userEmail);
    return { success: true, action: 'sendGChatDM', to: params.userEmail };
  } catch (e) {
    return { success: false, error: 'sendGChatDM: ' + e.message };
  }
}


// ─────────────────────────────────────────────────────────────────────────────
//  5. LOG TO GOOGLE SHEET
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Append a row to a Google Sheet.
 *
 * params:
 *   sheetId    — Spreadsheet ID from the URL
 *   sheetName  — tab name (default: Sheet1)
 *   columns    — comma-separated param keys to use as columns
 *                e.g. "number,short_description,priority"
 */
function logToSheet(params) {
  params = params || {};
  var sheetId = params.sheetId || params.spreadsheetId;
  if (!sheetId) {
    return { success: false, error: 'logToSheet: sheetId is required' };
  }

  var ss        = SpreadsheetApp.openById(sheetId);
  var sheetName = params.sheetName || 'Sheet1';
  var sheet     = ss.getSheetByName(sheetName) || ss.getActiveSheet();
  var now       = new Date().toISOString();
  var row;

  if (params.columns) {
    var cols = params.columns.split(',').map(function(c) { return c.trim(); });
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['timestamp'].concat(cols));
    }
    row = [now].concat(cols.map(function(c) { return params[c] !== undefined ? params[c] : ''; }));
  } else {
    row = [now, JSON.stringify(params)];
  }

  sheet.appendRow(row);
  Logger.log('logToSheet → row appended to ' + sheetId);
  return { success: true, action: 'logToSheet', sheetId: sheetId };
}


// ─────────────────────────────────────────────────────────────────────────────
//  6. CREATE GOOGLE DOC
// ─────────────────────────────────────────────────────────────────────────────

function createDoc(params) {
  params = params || {};
  var title    = params.title || 'AppScript Bridge Doc — ' + new Date().toLocaleDateString();
  var bodyText = params.body  || JSON.stringify(params, null, 2);

  var doc  = DocumentApp.create(title);
  var body = doc.getBody();
  body.clear();
  body.appendParagraph(title).setHeading(DocumentApp.ParagraphHeading.HEADING1);
  body.appendParagraph(bodyText);
  doc.saveAndClose();

  if (params.folderId) {
    var file   = DriveApp.getFileById(doc.getId());
    var folder = DriveApp.getFolderById(params.folderId);
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file);
  }

  Logger.log('createDoc → ' + doc.getId());
  return { success: true, action: 'createDoc', docId: doc.getId(), url: doc.getUrl() };
}


// ─────────────────────────────────────────────────────────────────────────────
//  WEB APP ENTRY  (doPost / doGet)
// ─────────────────────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    var params = JSON.parse(e.postData.contents);
    var result = handleEvent(params);
    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'AppScript Bridge active', version: 6 }))
    .setMimeType(ContentService.MimeType.JSON);
}


// ─────────────────────────────────────────────────────────────────────────────
//  PRIVATE HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function _resolveSpaceId(raw) {
  if (!raw) return null;
  if (raw.indexOf('spaces/') === 0) return raw;
  var m = raw.match(/\/room\/([^\/\?#]+)/);
  if (m) return 'spaces/' + m[1];
  return 'spaces/' + raw;
}

function _chatApiPost(url, payload) {
  var token = ScriptApp.getOAuthToken();
  var resp  = UrlFetchApp.fetch(url, {
    method:             'post',
    contentType:        'application/json',
    headers:            { Authorization: 'Bearer ' + token },
    payload:            JSON.stringify(payload),
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('Chat API ' + code + ': ' + resp.getContentText());
  }
  return JSON.parse(resp.getContentText());
}

function _chatApiGet(url) {
  var token = ScriptApp.getOAuthToken();
  var resp  = UrlFetchApp.fetch(url, {
    method:             'get',
    headers:            { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() !== 200) return null;
  return JSON.parse(resp.getContentText());
}

function _buildKVWidgets(params) {
  var widgets = [];
  var skip = ['action','spaceId','space','chatSpace','message','text','title','subtitle',
              'body','buttonLabel','buttonUrl','threadKey','recipient','to','email',
              'subject','htmlBody','cc','bcc','sheetId','spreadsheetId','sheetName',
              'columns','folderId','userEmail'];

  for (var i = 1; i <= 10; i++) {
    var lKey = 'field' + i + 'Label';
    var vKey = 'field' + i + 'Value';
    if (params[lKey] && params[vKey] !== undefined) {
      widgets.push({ keyValue: { topLabel: params[lKey], content: String(params[vKey]) } });
    }
  }

  if (widgets.length === 0) {
    Object.keys(params).forEach(function(k) {
      if (skip.indexOf(k) === -1 && params[k] !== '' && params[k] !== undefined) {
        widgets.push({ keyValue: { topLabel: k, content: String(params[k]) } });
      }
    });
  }
  return widgets;
}
