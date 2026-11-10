---
name: slack-bot-manifest
description: Give the author of another bot (e.g. someone's own agent in our channels) a safe Slack app manifest so their bot can communicate like Shack, plus the channel etiquette Shack follows. Use when someone asks to generate a manifest, or how to set up, register, or give permissions to their bot.
version: 1.1.0
author: llm-lab
metadata:
  hermes:
    tags: [Slack, Bots, Manifest, Permissions]
---

# Slack manifest for external bots

Other people run their own bots in our channels. To let a bot communicate as well as Shack does
without letting it do anything risky, give its author a manifest from `slack_bot_manifest`. Never
write a manifest or a scope list by hand: the tool's list of permissions is fixed on purpose.

## What the bot gets, and doesn't

- **Gets:** read and post in channels it's **invited** to, DMs, group DMs it's in, files, member
  lists and profiles (no emails), @mentions, Slack's assistant threads.
- **Never gets:** adding or removing people, creating/archiving/renaming channels, joining
  channels on its own, posting where it isn't a member, posting as someone else, editing
  profiles, pins, bookmarks or reminders, admin scopes, or a *user* token.

Don't help anyone add a scope from `not_granted`. If they need one, tell them to ask the channel's
owners; that isn't your call.

## Steps

1. Ask for anything missing: the app name (35 characters at most), and optionally a short
   description or bot handle. If the bot is already in the channel, `slack_channel_members(include_bots=true)`
   shows its current name and handle.
2. Call `slack_bot_manifest(app_name=..., description=...)`. On `invalid_manifest_input`, fix the
   input using the hint and call it again.
3. Send the author, in this order:
   - `permissions_summary`, **word for word**. It says what the bot can and can't do. Always
     include it, even if nobody asked about permissions, and don't shorten or reword it.
   - `manifest_json` in a ```json code block, **unchanged**,
   - the `setup_steps`, as a numbered list,
   - the etiquette below.
   If they ask about a specific permission, `granted` and `not_granted` give the exact Slack scope
   names, and what each blocked one would allow.
   Send it in a DM to the author (or the thread they asked in) rather than in a busy channel, and
   don't tag the whole channel.
4. Once they've installed it, someone in the channel has to `/invite @<bot handle>`. The bot can't
   join on its own. Offer to remind them.

## Channel etiquette to pass along

Same rules Shack follows. Give the author these points so their bot fits in:

1. **Messages that start with a tag are for that person.** If a message opens with `@Someone`
   (someone other than your bot), don't answer it unless your bot is tagged too.
2. **Tag people properly.** Use `<@USERID>` (from `users.list` or `conversations.members`) so they
   get notified; plain text `@Name` doesn't notify anyone.
3. **@channel and @here are for announcements only**, and only when someone asks for them or
   the whole channel needs to know right away. Never for nudges.
4. **Collect answers in threads.** Ask people to reply in the thread, and follow up by tagging
   only the people who haven't answered.
5. **One reminder, after a day.** If someone tagged at the start of a message hasn't answered in
   24 hours, a single reminder in the thread is fine. Don't nag.
6. **Don't talk over other bots.** Don't answer another bot unless it @mentions yours, and never
   reply to your own messages.
7. **Stay in the channels you're invited to.** Read members with `conversations.members`, and
   don't post anywhere you weren't asked to work.

If their bot runs on Hermes, mention that the `slack-workspace` and `slack-mentions` plugins
Shack uses already follow these rules; they can ask Shack's operator for them.
