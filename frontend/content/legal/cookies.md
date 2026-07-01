[//]: # (TODO: Replace paperspod.privacy@gmail.com with privacy@[custom domain] once domain is live)

# Cookie Policy

*Last Updated: July 1, 2026*

Our [Privacy Policy](/privacy) explains our broader principles about collecting and using your information. This policy explains specifically how PapersPod and the third-party services we use deploy cookies and similar technologies.

*Adapted from [Automattic's Cookie Policy](https://github.com/automattic/legalmattic) under the [Creative Commons Sharealike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license.*

---

## What Are Cookies?

Cookies are small text files stored on your device when you visit a website. They allow sites to recognize you across page loads and between sessions, remember your preferences, and keep you logged in. Both websites and HTML emails may also use related technologies such as web beacons (small transparent tracking images) and browser local storage.

Cookies may be set by the site you are visiting ("first-party cookies") or by third-party services embedded in or powering that site ("third-party cookies").

## How We Use Cookies

PapersPod uses cookies primarily for **authentication and session management**. We do not use cookies to show you targeted advertising, and we do not share cookie data with advertising networks.

### Required Cookies

These cookies are necessary for the Services to function. Without them, you cannot sign in or stay logged in.

| Cookie | Set by | Purpose |
|--------|--------|---------|
| `__clerk_db_jwt` | Clerk | Stores your authentication session token. Required to remain logged in across page loads. |
| `__session` | Clerk | Session identifier used by Clerk to manage your active login session. |
| `__client_uat` | Clerk | Tracks the last user activity timestamp to manage session expiry. |

These cookies are session-persistent and are cleared when you sign out or when the session expires.

### Analytics and Performance

We may use first-party analytics to understand how users interact with PapersPod — for example, which pages are visited and how episodes are discovered. If we implement third-party analytics (such as a usage measurement service), we will list those services and their cookies in this policy before deployment.

**Currently, we do not use third-party analytics cookies.**

### Future: Blog and Comment Features

If PapersPod adds blog publishing or comment features in the future, additional cookies may be set to remember comment author information (name, email, URL) and subscription preferences for new comments on posts you have participated in. This policy will be updated before those features go live.

## Third-Party Cookies

The primary third-party cookie-setter in our stack is **Clerk**, which manages authentication. Clerk's practices are described in their [Privacy Policy](https://clerk.com/legal/privacy).

PapersPod does not operate an advertising program and does not allow advertising networks to set cookies on our site.

## Where Cookies Are Set

Cookies are set on:

- Our web application (paperspod.vercel.app and any future custom domain)
- Our API (paperspod.fly.dev), for authenticated API calls

## Controlling Cookies

You can control and delete cookies through your browser settings. Most browsers let you:

- View cookies currently stored for a site;
- Block cookies from specific sites or from third parties; or
- Delete all cookies when you close the browser.

**Note:** Blocking or deleting required authentication cookies (the Clerk cookies listed above) will prevent you from signing in to PapersPod or staying signed in between sessions.

For general information on managing and deleting cookies, visit [aboutcookies.org](https://www.aboutcookies.org).

If you have opted out of analytical tracking through your browser's "Do Not Track" signal, we will honor it for any first-party analytics we deploy.

## Our Use of Local Storage

In addition to cookies, PapersPod's audio player uses **browser local storage** to persist a session identifier between page loads. This identifier is used solely to attribute play events (start, pause, completion) to a single listening session for usage analytics. It is not linked to your account and is not shared with third parties.

## Contact

For questions about our use of cookies or tracking technologies:

**Email:** paperspod.privacy@gmail.com

---

*Adapted from Automattic's Cookie Policy, available at [github.com/automattic/legalmattic](https://github.com/automattic/legalmattic), under the [Creative Commons Sharealike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. Revisions reflect PapersPod's actual cookie practices.*
