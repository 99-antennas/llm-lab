---
name: slack-workspace
description: See who is in a Slack channel, ask channel members questions with real @tags, and collect their answers. Use for "who's here", headcounts, "ask everyone…", polls, check-ins, and following up on who hasn't replied.
version: 1.2.0
author: llm-lab
metadata:
  hermes:
    tags: [Slack, Channels, Members, Questions]
---

# Slack workspace: members, tagged questions, collecting answers

Use these tools for questions about channel membership. Never guess from the conversation history,
because quiet members never show up there.

## Tools

- `slack_channel_members(channel?, include_bots?)`: who is in a channel. Leave out `channel` to
  get the current Slack channel. `channel` accepts an ID (`C0123ABCD`), `#name` or `name`.
- `slack_list_channels(query?)`: the channels Shack belongs to, with IDs, privacy and topics. Use `slack_channel_members` for counts.
- `slack_post_message(text, channel?, mention?, thread_ts?, broadcast?)`: post to an allowed
  channel with real tags, so people get notified. `@Name` in the text becomes a tag,
  `mention="all"` tags everyone in the channel, and `broadcast="channel"` or `"here"` adds a real
  @channel or @here. Returns `ts`.
- `slack_get_replies(ts, channel?)`: answers to a posted message (thread replies plus channel
  messages from the people it tagged), and `waiting_on`, the tagged people who haven't answered.

Posting and reading replies only work in the channels the operator allows (`channel_not_allowed`
otherwise). Don't try to work around that.

## Asking people questions and gathering answers

1. Get the people with `slack_channel_members(channel)`.
2. Post one clear question with `slack_post_message`:
   - **Everyone:** `mention="all"` and a question like "Which weekend works for you: Mar 6–8 or
     Mar 13–15? Reply in this thread 🧵".
   - **Specific people:** write `@Name` for each person, using names exactly as
     `slack_channel_members` returned them.
   - **A different question for each person:** post one message per person, each tagging only them.
   - Ask people to **reply in the thread**, so the answers stay together.
3. Write down the returned `ts` (and channel) in your reply or memory. You need it to collect answers
   later, possibly in a later conversation.
4. When asked for results, call `slack_get_replies(ts)`. Summarize who said what, and list
   `waiting_on`. To nudge, reply in the thread with `thread_ts=ts`, tagging only the people in
   `waiting_on`.

### @channel and @here

`broadcast` is the only way to send @channel or @here. Without it, writing "@channel" or
`<!channel>` in the text posts plain text that notifies nobody.
- `broadcast="channel"` notifies everyone in the channel. Use it for announcements the whole
  channel must see: decisions, deadlines, schedule changes.
- `broadcast="here"` notifies only people who are online right now. Use it for time-sensitive asks.
- To **collect answers**, prefer `mention="all"`. It notifies the same people and makes it clear who
  was asked. `slack_get_replies` still tracks a broadcast question against everyone in the channel.
- Only broadcast when the user asks for it or the message really needs everyone's attention right
  away. Never broadcast nudges or follow-ups; tag only the people in `waiting_on`.

Don't post twice: if you posted the question with `slack_post_message` into the channel you're
talking in, keep your own reply short ("Posted, I'll collect the answers") and don't repeat the
question or the tags.

If the post fails with `unknown_members`, nothing was posted. Fix the names using
`channel_members` from the error, then try again. Never post with a broken tag, because that person
wouldn't be notified.

## Answering membership questions

- "Who's in this channel?" or "how many people are here?": call `slack_channel_members()` with no
  arguments, then report `member_count` and the names. People and bots are counted separately; bots
  are left out unless `include_bots` is true.
- In a normal reply, tag someone by writing `@Name` (it becomes a real mention) or by copying their
  `mention` field (`<@U…>`) exactly.
- For a long list (more than about 25 people), summarize it, for example by title or timezone, and
  offer the full list.

## Errors

The tools return `{"error": ..., "hint": ...}`. Pass the hint on to the user in plain words:
- `not_in_channel` / `channel_not_found`: Shack can't see that channel. Private channels need
  `/invite @Shack`.
- `channel_not_allowed`: Shack isn't allowed to post there. `allowed_channels` lists where it can.
- `missing_scope`: the Slack app needs the scope in `needed_scope` added and the app reinstalled.
