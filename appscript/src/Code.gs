/**
 * AppScript Bridge — Universal Handler
 *
 * This is the main entry point. AppScript Bridge calls handleEvent(params)
 * with the resolved parameter mapping you configured in the workflow editor.
 *
 * params object always includes:
 *   params.action   — what to do: "sendEmail" | "sendGChatMessage" | "sendGChatCard" | "logToSheet" | "createDoc"
 *   params.*        — any fields you mapped from the trigger payload
 *
 * You can also call individual functions directly from the workflow editor
 * by setting the function name in the Action node.
 */

// ─────────────────────────────────────────────────────────────────────────────
//  UNIVERSAL DISPATCHER
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Called by AppScript Bridge for every workflow execution.
 * Route to the correct handler based on params.action.
 *
 * Example parameter mapping in AppScript Bridge:
 *   action        → "sendGChatMessage"
 *   spaceId       → {{payload.chat.id}}   or a hardcoded space name
 *   message       → "New incident: {{payload.number}} - {{payload.short_description}}"
 */
function handleEvent(params) {
  try {
    var action = (params && params.action) ? params.action : 'sendEmail';

    switch (action) {
      case 'sendEmail':         return sendEmail(params);
      case 'sendGChatMessage':  return sendGChatMessage(params);
      case 'sendGChatCard':     return sendGChatCard(params);
      case 'sendGChatDM':       return sendGChatDM(params);
      case 'logToSheet':        return logToSheet(params);
      case 'createDoc':         return createDoc(params);
      case 'createSheetRow':    return createSheetRow(params);
      default:
        return { success: false, error: 'Unknown action: ' + action };
    }
  } catch (e) {
    Logger.log('handleEvent error: ' + e.message);
    return { success: false, error: e.message };
  }
}


// ─────────────────────────────────────────────────────────────────────────────
//  1. SEND EMAIL
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Send an email via GmailApp (uses https://mail.google.com/ scope).
 *
 * params:
 *   recipient  — email address (required)
 *   subject    — email subject
 *   body       — plain-text body
 *   htmlBody   — (optional) HTML body
 *   cc         — (optional) CC address
 *   bcc        — (optional) BCC address
 *   name       — (optional) sender display name
 *   replyTo    — (optional) reply-to address
 */
function sendEmail(params) {
  var recipient = params.recipient || params.to || params.email;
  if (!recipient) {
    return { success: false, error: 'sendEmail: recipient is required (map it from payload)' };
  }

  var subject = params.subject || '[AppScript Bridge] Notification';
  var body    = params.body    || JSON.stringify(params, null, 2);

  var options = {};
  if (params.htmlBody) options.htmlBody    = params.htmlBody;
  if (params.cc)       options.cc          = params.cc;
  if (params.bcc)      options.bcc         = params.bcc;
  if (params.name)     options.name        = params.name;
  if (params.replyTo)  options.replyTo     = params.replyTo;

  // Use GmailApp — requires https://mail.google.com/ scope (declared in appsscript.json)
  // Falls back to MailApp if GmailApp is somehow unavailable
  try {
    GmailApp.sendEmail(recipient, subject, body, options);
    Logger.log('sendEmail (GmailApp) → ' + recipient + ' | ' + subject);
  } catch (gmailErr) {
    Logger.log('GmailApp failed, trying MailApp: ' + gmailErr.message);
    try {
      MailApp.sendEmail(recipient, subject, body, options);
      Logger.log('sendEmail (MailApp) → ' + recipient + ' | ' + subject);
    } catch (mailErr) {
      return {
        success: false,
        error: 'Email failed. Re-authorize the script: open script.google.com → Run any function → Allow permissions. Details: ' + mailErr.message
      };
    }
  }

  return { success: true, action: 'sendEmail', to: recipient, subject: subject };
}


// ─────────────────────────────────────────────────────────────────────────────
//  2. GOOGLE CHAT — Send a text message to a Space
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Post a plain text message to a Google Chat Space using the Chat REST API.
 *
 * params:
 *   spaceId  — Chat space name, e.g. "spaces/XXXXXXXXX"
 *              OR a full space URL: https://chat.google.com/room/XXXXXXXXX
 *   message  — text to post (supports basic markdown)
 *   threadKey — (optional) reply to a thread
 *
 * How to find your spaceId:
 *   Open Google Chat → click a space → look at the URL:
 *   https://mail.google.com/chat/u/0/#chat/space/XXXXXXXXX
 *   Your spaceId = "spaces/XXXXXXXXX"
 */
function sendGChatMessage(params) {
  var spaceId = _resolveSpaceId(params.spaceId || params.space || params.chatSpace);
  if (!spaceId) {
    return { success: false, error: 'sendGChatMessage: spaceId is required' };
  }

  var text = params.message || params.text || JSON.stringify(params, null, 2);

  var payload = { text: text };
  if (params.threadKey) payload.thread = { threadKey: params.threadKey };

  var url = 'https://chat.googleapis.com/v1/' + spaceId + '/messages';
  var response = _chatApiPost(url, payload);

  Logger.log('sendGChatMessage → ' + spaceId);
  return { success: true, action: 'sendGChatMessage', space: spaceId, response: response };
}


// ─────────────────────────────────────────────────────────────────────────────
//  3. GOOGLE CHAT — Send a rich Card message
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Post a formatted Card to Google Chat (great for incident notifications).
 *
 * params:
 *   spaceId      — Chat space name
 *   title        — card title
 *   subtitle     — card subtitle
 *   body         — main body text (shown as a paragraph)
 *   fields       — array of {label, value} pairs shown as key-value rows
 *                  OR pass individual: field1Label, field1Value, field2Label, field2Value
 *   color        — header color hex (default: Astreya purple #7c3aed)
 *   buttonLabel  — (optional) action button label
 *   buttonUrl    — (optional) action button URL
 *   threadKey    — (optional) thread key for threading
 *
 * Example parameter mapping in AppScript Bridge:
 *   title        → "Incident {{payload.number}}"
 *   subtitle     → "{{payload.short_description}}"
 *   body         → "Priority: {{payload.priority}} | State: {{payload.state}}"
 *   buttonLabel  → "View in ServiceNow"
 *   buttonUrl    → "https://your-instance.service-now.com/incident.do?sysparm_query=number={{payload.number}}"
 */
function sendGChatCard(params) {
  var spaceId = _resolveSpaceId(params.spaceId || params.space || params.chatSpace);
  if (!spaceId) {
    return { success: false, error: 'sendGChatCard: spaceId is required' };
  }

  var headerColor = params.color || '#7c3aed';
  var title       = params.title    || 'AppScript Bridge Notification';
  var subtitle    = params.subtitle || '';
  var bodyText    = params.body     || '';

  // Build sections
  var sections = [];

  // Main body paragraph
  if (bodyText) {
    sections.push({
      widgets: [{ textParagraph: { text: bodyText } }]
    });
  }

  // Key-value fields
  var kvWidgets = _buildKVWidgets(params);
  if (kvWidgets.length > 0) {
    sections.push({ widgets: kvWidgets });
  }

  // Action button
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
      title:      title,
      subtitle:   subtitle,
      imageUrl:   'https://www.gstatic.com/images/branding/product/1x/apps_script_48dp.png',
      imageStyle: 'IMAGE'
    },
    sections: sections
  };

  var msgPayload = { cards: [card] };
  if (params.threadKey) msgPayload.thread = { threadKey: params.threadKey };

  var url = 'https://chat.googleapis.com/v1/' + spaceId + '/messages';
  var response = _chatApiPost(url, msgPayload);

  Logger.log('sendGChatCard → ' + spaceId + ' | ' + title);
  return { success: true, action: 'sendGChatCard', space: spaceId, title: title };
}


// ─────────────────────────────────────────────────────────────────────────────
//  4. GOOGLE CHAT — Send a Direct Message
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Send a DM to a specific user in Google Chat.
 *
 * params:
 *   userEmail  — Google Workspace email of the recipient
 *   message    — text to send
 */
function sendGChatDM(params) {
  if (!params.userEmail) {
    return { success: false, error: 'sendGChatDM: userEmail is required' };
  }

  // Create a DM space first, then post
  var dmPayload = { name: 'me', singleUserBotDm: true };
  try {
    // Find or create a DM space with the user
    var createUrl = 'https://chat.googleapis.com/v1/spaces:findDirectMessage?name=users/' + params.userEmail;
    var spaceResp = _chatApiGet(createUrl);
    var spaceId   = spaceResp && spaceResp.name ? spaceResp.name : null;

    if (!spaceId) {
      return { success: false, error: 'sendGChatDM: could not find DM space for ' + params.userEmail };
    }

    var text = params.message || params.text || 'Notification from AppScript Bridge';
    var url  = 'https://chat.googleapis.com/v1/' + spaceId + '/messages';
    _chatApiPost(url, { text: text });

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
 *   sheetId    — Spreadsheet ID (from the URL)
 *   sheetName  — Tab name (default: "Sheet1")
 *   columns    — comma-separated list of param keys to use as columns
 *                e.g. "number,short_description,priority,state"
 *                If omitted, all params are written as JSON
 */
function logToSheet(params) {
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
    row = cols.map(function(c) { return params[c] || ''; });
    row.unshift(now); // prepend timestamp

    // Add header row if sheet is empty
    if (sheet.getLastRow() === 0) {
      var header = ['timestamp'].concat(cols);
      sheet.appendRow(header);
    }
  } else {
    row = [now, JSON.stringify(params)];
  }

  sheet.appendRow(row);
  Logger.log('logToSheet → ' + sheetId + ' row appended');
  return { success: true, action: 'logToSheet', sheetId: sheetId, row: row };
}


// ─────────────────────────────────────────────────────────────────────────────
//  6. CREATE GOOGLE DOC
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create a new Google Doc with formatted content.
 *
 * params:
 *   title    — document title
 *   body     — document body text
 *   folderId — (optional) Drive folder ID to place the doc in
 */
function createDoc(params) {
  var title = params.title || 'AppScript Bridge Document - ' + new Date().toLocaleDateString();
  var body  = params.body  || JSON.stringify(params, null, 2);

  var doc   = DocumentApp.create(title);
  var docBody = doc.getBody();
  docBody.clear();
  docBody.appendParagraph(title).setHeading(DocumentApp.ParagraphHeading.HEADING1);
  docBody.appendParagraph(body);
  doc.saveAndClose();

  if (params.folderId) {
    var file   = DriveApp.getFileById(doc.getId());
    var folder = DriveApp.getFolderById(params.folderId);
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file);
  }

  Logger.log('createDoc → ' + doc.getId() + ' "' + title + '"');
  return { success: true, action: 'createDoc', docId: doc.getId(), title: title, url: doc.getUrl() };
}


// ─────────────────────────────────────────────────────────────────────────────
//  7. WEB APP ENTRY (doPost) — for Web App deployment mode
// ─────────────────────────────────────────────────────────────────────────────

/**
 * When deployed as a Web App, AppScript Bridge can POST directly here
 * without needing the Execution API (no GCP project link required).
 * Set action type to "Web App" in the workflow editor.
 */
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

function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'AppScript Bridge handler active' }))
    .setMimeType(ContentService.MimeType.JSON);
}


// ─────────────────────────────────────────────────────────────────────────────
//  PRIVATE HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function _resolveSpaceId(raw) {
  if (!raw) return null;
  // Already in correct format
  if (raw.indexOf('spaces/') === 0) return raw;
  // Extract from full URL: https://chat.google.com/room/XXXXX
  var m = raw.match(/\/room\/([^\/\?#]+)/);
  if (m) return 'spaces/' + m[1];
  // Bare ID
  return 'spaces/' + raw;
}

function _chatApiPost(url, payload) {
  var token = ScriptApp.getOAuthToken();
  var opts = {
    method:      'post',
    contentType: 'application/json',
    headers:     { Authorization: 'Bearer ' + token },
    payload:     JSON.stringify(payload),
    muteHttpExceptions: true
  };
  var resp = UrlFetchApp.fetch(url, opts);
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('Chat API error ' + code + ': ' + resp.getContentText());
  }
  return JSON.parse(resp.getContentText());
}

function _chatApiGet(url) {
  var token = ScriptApp.getOAuthToken();
  var opts = {
    method:  'get',
    headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true
  };
  var resp = UrlFetchApp.fetch(url, opts);
  if (resp.getResponseCode() !== 200) return null;
  return JSON.parse(resp.getContentText());
}

function _buildKVWidgets(params) {
  var widgets = [];
  var skip    = ['action','spaceId','space','chatSpace','message','text','title',
                 'subtitle','body','color','buttonLabel','buttonUrl','threadKey',
                 'recipient','to','email','subject','htmlBody','cc','bcc',
                 'sheetId','spreadsheetId','sheetName','columns','folderId',
                 'userEmail'];

  // Check for explicit fields array first
  if (params.fields && Array.isArray(params.fields)) {
    params.fields.forEach(function(f) {
      if (f.label && f.value) {
        widgets.push({ keyValue: { topLabel: f.label, content: String(f.value) } });
      }
    });
    return widgets;
  }

  // Otherwise use numbered field pairs: field1Label/field1Value
  for (var i = 1; i <= 10; i++) {
    var lKey = 'field' + i + 'Label';
    var vKey = 'field' + i + 'Value';
    if (params[lKey] && params[vKey]) {
      widgets.push({ keyValue: { topLabel: params[lKey], content: String(params[vKey]) } });
    }
  }

  // Fall back: all remaining params not in skip list
  if (widgets.length === 0) {
    Object.keys(params).forEach(function(k) {
      if (skip.indexOf(k) === -1 && params[k] !== undefined && params[k] !== '') {
        widgets.push({ keyValue: { topLabel: k, content: String(params[k]) } });
      }
    });
  }

  return widgets;
}
