[//]: # (TODO: Replace paperspod.privacy@gmail.com with privacy@[custom domain] once domain is live)

# Privacy Policy

*Last Updated: July 1, 2026*

Your privacy matters to us. A few core principles guide how we handle your information:

- We collect only what we need to provide our Services.
- We do not sell your personal information.
- We store personal information only as long as we have a reason to keep it.
- We aim for full transparency about what we collect, how we use it, and who we share it with.

*Adapted from [Automattic's Privacy Policy](https://github.com/automattic/legalmattic) under the [Creative Commons Sharealike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license.*

---

## Who We Are and What This Policy Covers

PapersPod is an AI-powered research podcast service. This Privacy Policy applies to information we collect when you use our website and web application (currently at paperspod.vercel.app and paperspod.fly.dev), and any related services (collectively, "Services").

## Information We Collect

We collect information from three sources: information you provide directly, information collected automatically as you use our Services, and information we receive from third-party services you use to access our platform.

### Information You Provide to Us

**Account information.** When you create an account, we collect your email address and display name through our authentication provider, Clerk. You do not need to provide additional profile information, but you may do so if you choose.

**Episode parameters.** When you create an episode, we store the configuration you submit: topic, academic disciplines, expertise level, and any other options you specify. This data is associated with your account and retained to allow you to access your episodes.

**Feedback.** If you submit feedback (bug reports, feature suggestions, or positive feedback), we store the feedback type and the text content of your submission, associated with your account.

**API keys.** If you provide API keys for third-party AI providers, those keys are stored encrypted in our database. We do not store API keys in plaintext, and we never return your full key after submission. Only a masked hint is displayed.

**Communications.** If you contact us for support, we retain a copy of that communication.

### Information Collected Automatically

**Log information.** Our servers log standard web request information, including IP address, browser type, operating system, referring URL, and the date and time of each request.

**Usage information.** We collect information about how you interact with our Services. Currently this includes: which episodes you create, play events (start, pause, resume, stop), and estimated listening completion percentage. As the platform develops, we will expand behavioral data collection to include additional engagement signals — such as whether you click through to view a source paper, which portions of an episode you replay or skip, and other listening and navigation behaviors. These signals will be used to improve the Services and to build a recommendation engine over time. The specific signals we collect will grow as our data infrastructure develops; we will update this policy to reflect material additions before collecting new categories of data.

**Device information.** We may collect information about the device and browser you use to access the Services, such as screen resolution and browser version.

**Cookies and similar technologies.** We use cookies and similar technologies primarily for authentication. See our [Cookie Policy](/cookies) for details.

### Information From Third Parties

**Authentication.** We use Clerk for authentication. When you sign in, Clerk provides us with a user identifier and basic profile information (email address, display name).

**Third-party login.** If you sign in using a third-party provider such as Google, we receive associated login information from that provider via Clerk.

## How and Why We Use Information

We use information about you for the following purposes:

**To provide our Services.** To create and maintain your account, generate episodes, track your credit balance, deliver audio content, and provide support.

**To operate the credit system.** To record credit balances, deduct credits for episode generation, award credits for feedback, and enforce weekly feedback caps.

**To improve our Services.** To understand how users interact with PapersPod, diagnose problems, and develop new features.

**To power recommendations.** We are building a recommendation system to surface relevant episodes and papers. This system currently uses content-based signals (vector embeddings of episode text, generated via OpenAI) to identify related episodes. Over time, it will incorporate behavioral signals — such as listening completion rates, paper link click-throughs, and other engagement data — to improve recommendation quality. Recommendation data is not used for advertising and is not shared with advertising networks.

**To communicate with you.** To send important account updates, respond to support requests, and notify you of changes to our Terms or this Policy. We may also send you marketing communications if you have opted in; you may opt out at any time.

**To protect against fraud and abuse.** To detect suspicious activity, prevent abuse of the credit system, and comply with legal obligations.

### Legal Bases for Processing (European Users)

For users in the European Economic Area, our legal bases for processing personal information are:

1. **Contract performance** — processing necessary to provide the Services you requested and maintain your account;
2. **Legitimate interests** — improving our Services, preventing fraud, generating recommendations, and communicating with users about service updates;
3. **Legal obligation** — where required by applicable law; and
4. **Consent** — where you have given explicit consent, such as for certain cookie uses or marketing communications.

## Sharing Information

We do not sell your personal information. We share information only in the following circumstances:

**Service providers.** We share information with third-party vendors who help us operate the Services. These include:

| Provider | Role | Data Shared |
|----------|------|-------------|
| Clerk | Authentication and session management | Email address, display name, device/session info |
| Anthropic | AI script generation | Episode topic and parameters, fetched paper content (no account identifiers) |
| ElevenLabs | Voice synthesis | Script text only (no account identifiers) |
| Cloudflare R2 | Audio and script file storage | Episode audio files, script files |
| Fly.io | Application hosting | All request traffic transits through Fly.io infrastructure |
| Neon | Database | All structured data: account info, episode records, credit events |
| OpenAI | Content embeddings | Episode content text (no account identifiers) |

Each provider operates under its own privacy policy and data processing terms. We require our service providers to handle your information appropriately.

**Legal requirements.** We may disclose information in response to a lawful court order, subpoena, or government request. We will notify you of such requests where legally permitted to do so.

**Protection of rights.** We may disclose information if we believe in good faith that disclosure is necessary to protect the rights, property, or safety of PapersPod, our users, or the public.

**Business transfers.** If PapersPod is acquired, merged with another entity, or goes through a similar transaction, user information may be transferred as part of that transaction. We will notify you of any such transfer and provide you with an opportunity to delete your account.

**With your consent.** We may share information in other circumstances with your explicit consent.

**Aggregated or de-identified data.** We may publish anonymized aggregate statistics about usage patterns that cannot reasonably be used to identify you.

## How Long We Keep Information

We retain your information as long as your account is active or as needed to provide the Services. If you request account deletion, we will delete or anonymize your personal information within a reasonable period, subject to any legal obligations to retain certain records.

Episode audio files and scripts are stored on Cloudflare R2. We retain these as long as your account is active and you have not deleted the episode. Deleted episodes are removed from storage, though cached content may persist briefly.

Server logs are typically retained for approximately 30 days.

## Security

We implement reasonable technical and organizational measures to protect your information against unauthorized access, use, alteration, or destruction. These measures include:

- Encrypted storage of sensitive data (including API keys)
- HTTPS for all traffic in transit
- Access controls on our database
- Authentication managed through Clerk, a dedicated authentication provider

No online service is completely secure, and we cannot guarantee the absolute security of your information. You are responsible for maintaining the security of your account credentials.

## Your Choices

**Account information.** You can update your account information through Clerk's account management interface.

**Episode data.** You can delete episodes you have generated. Deletion removes them from our database and storage within a short period.

**Marketing communications.** If we send marketing communications, you may opt out at any time by following the unsubscribe instructions in those messages. We will still send you service-related communications necessary for account management.

**Cookies.** You can control cookie behavior through your browser settings. See our [Cookie Policy](/cookies) for details. Note that blocking authentication cookies will prevent you from signing in.

**Close your account.** You may request account deletion by contacting us. We will delete your personal information, subject to any legal retention requirements. Note that closing your account forfeits any remaining credits.

## Your Rights

### European Users (GDPR)

If you are located in the European Economic Area, Switzerland, or the United Kingdom, you have the following rights with respect to your personal information, subject to applicable exemptions:

- **Right of access** — to request a copy of the personal information we hold about you;
- **Right to rectification** — to request correction of inaccurate or incomplete information;
- **Right to erasure** — to request deletion of your personal information;
- **Right to restrict processing** — to request that we limit how we use your information;
- **Right to data portability** — to receive your information in a structured, machine-readable format;
- **Right to object** — to object to our processing of your information based on legitimate interests; and
- **Right to lodge a complaint** — with your local data protection supervisory authority.

To exercise these rights, contact us using the information in the "How to Reach Us" section below.

### US State Privacy Rights

If you are a California resident or a resident of another US state with applicable privacy laws, you may have the following rights, subject to applicable exemptions:

- Know what personal information we collect, how we use it, and with whom we share it;
- Request deletion of your personal information;
- Request correction of inaccurate personal information;
- Opt out of the sale or sharing of personal information (we do not sell personal information);
- Receive a portable copy of your information; and
- Not be discriminated against for exercising your privacy rights.

**We do not sell personal information** within the meaning of the California Consumer Privacy Act or any other applicable US state privacy law.

**Categories of personal information collected in the past 12 months:**
- Identifiers (email address, display name, user ID, IP address, session identifiers)
- Internet or electronic network activity information (episode creation activity, play events, estimated listening completion; additional engagement signals as described in the Information We Collect section above)
- Inferences (related-episode recommendations based on content and, as developed, behavioral signals)

**Sources:** Information you provide directly; information collected automatically through your use of the Services; information from Clerk (authentication provider).

**Purposes:** To provide the Services; to operate the credit system; to improve the Services; to generate recommendations; to communicate with you; to protect against fraud.

**Categories of third parties with whom we share information:** Service providers (as listed in the Sharing Information section above).

### Appeals Process

If we deny a privacy rights request, we will explain the reason in writing. You may appeal by responding to our written denial within 30 days. Appeals will be reviewed by a person not involved in the original decision. If your appeal is denied, you may have the right to contact your state's attorney general or relevant data protection authority.

## Controllers and Responsible Parties

PapersPod is operated as a US-based service. If you are located in the European Economic Area and have questions about which entity is responsible for processing your information, please contact us.

## How to Reach Us

For privacy questions, rights requests, or account deletion:

**Email:** paperspod.privacy@gmail.com

We aim to respond to privacy-related inquiries within 30 days.

## Other Things You Should Know

### Third-Party Services

This Privacy Policy covers only PapersPod's collection and use of your information. When you use our Services, you interact with third-party services (Clerk, Anthropic, ElevenLabs, Cloudflare, Fly.io, Neon, OpenAI) that have their own privacy practices. We encourage you to review their privacy policies.

### AI Processing

When you generate an episode, your topic and episode parameters are sent to Anthropic for script generation, and the resulting script text is sent to ElevenLabs for voice synthesis. We do not send personally identifying information (such as your name, email address, or user ID) to Anthropic or ElevenLabs as part of this process.

If you provide your own API keys for third-party AI providers, your episode generation requests may be processed by those providers in accordance with your direct agreement with them.

### Future Blog and Comment Features

If PapersPod adds blog publishing or comment features, content you publish publicly will be publicly visible and may be indexed by search engines. This policy will be updated before any such features are launched.

## Changes to This Policy

We may update this Privacy Policy from time to time. If we make material changes, we will notify you by email or through the Services and update the "Last Updated" date. Minor changes may take effect upon posting. Your continued use of the Services after changes take effect constitutes acceptance of the updated Policy.

---

*Adapted from Automattic's Privacy Policy, available at [github.com/automattic/legalmattic](https://github.com/automattic/legalmattic), under the [Creative Commons Sharealike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. Revisions reflect PapersPod's actual data practices.*
