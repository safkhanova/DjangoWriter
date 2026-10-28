// emailotp.js — login / register / verify pages.
// Replaces the duplicated inline <script> blocks that were in login.html
// and register.html.

document.addEventListener('DOMContentLoaded', function () {
    var card = document.querySelector('.emailotp-card');
    if (!card) return;   // not an auth page

    // --- show/hide password ---------------------------------------------
    card.querySelectorAll('input[type="password"]').forEach(function (input) {
        var wrap = document.createElement('span');
        wrap.className = 'emailotp-pw-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'emailotp-pw-toggle';
        btn.textContent = '👁';
        btn.setAttribute('aria-label', 'Show password');
        btn.addEventListener('click', function () {
            var shown = input.type === 'text';
            input.type = shown ? 'password' : 'text';
            btn.textContent = shown ? '👁' : '🙈';
        });
        wrap.appendChild(btn);
    });

    // --- the 6-digit code field -----------------------------------------
    var code = card.querySelector('input[name="code"]');
    if (code) {
        code.focus();
        // phone keyboards open on digits; browsers offer the SMS/email code
        code.setAttribute('inputmode', 'numeric');
        code.setAttribute('autocomplete', 'one-time-code');
        code.setAttribute('pattern', '[0-9]*');

        // strip anything non-numeric, e.g. spaces from a pasted code
        code.addEventListener('input', function () {
            var cleaned = code.value.replace(/\D/g, '');
            if (cleaned !== code.value) code.value = cleaned;
        });
    }

    // --- don't let an impatient click send two codes ----------------------
    card.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                // re-enable if the user comes back via the bfcache
                setTimeout(function () { btn.disabled = false; }, 4000);
            }
        });
    });
});