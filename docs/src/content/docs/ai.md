---
title: AI model providers
description: Connect OpenAI, OpenRouter, Anthropic, Gemini, Ollama, and OpenAI-compatible providers to REL Chat.
editUrl: false
---
REL's native Chat can use OpenAI, OpenRouter, Anthropic, Gemini, Ollama, or a
generic OpenAI-compatible service. Provider profiles keep routing and model
settings in REL while API keys stay in macOS Keychain.

## Add an OpenRouter provider

1. Open **REL → Settings… → Providers**.
2. Add a provider and choose **OpenRouter**.
3. Enter a profile name and your OpenRouter API key.
4. Refresh the model list, select a model, and save the provider.
5. Choose that model in Chat or make it the default model.

REL connects to `https://openrouter.ai/api/v1` by default and sends the API key
as bearer authentication. You do not need to enter an endpoint. If your
OpenRouter account requires a different API hostname, use **Advanced → Endpoint
Override** on the provider profile. REL caps each OpenRouter completion at
4,096 output tokens so the provider does not reserve an upstream model's much
larger maximum against the key's credit limit.

OpenRouter model IDs include the upstream provider, for example
`openai/gpt-5.6-sol`. REL loads the available IDs from OpenRouter instead of
maintaining a fixed catalog. See [OpenRouter's model
documentation](https://openrouter.ai/docs/guides/overview/models) for routing
and availability details.

## Provider behavior

| Provider | API path | API key | Endpoint |
| --- | --- | --- | --- |
| OpenAI | Responses | Required | Built in |
| OpenRouter | Chat Completions | Required | Built in; advanced override available |
| Anthropic | Native | Required | Built in; advanced override available |
| Gemini | Native | Required | Built in; advanced override available |
| Ollama | Native | Not required | Built in; advanced override available |
| OpenAI-compatible | Chat Completions | Optional | Required |

First-party OpenAI profiles cannot be changed into compatible endpoints by an
endpoint override. Use **OpenRouter** or **OpenAI-compatible** when Chat
Completions compatibility is the intended trust boundary.

REL currently marks image tool results as unsupported for OpenRouter and other
OpenAI-compatible Chat Completions profiles. Browser tools still return page
semantics, so the model can read and operate ordinary pages; requests that
explicitly require visual image observations return an unsupported-modality
error instead of silently dropping the image.

## Credentials and saved settings

REL saves every profile's API key as a per-profile generic-password item in
macOS Keychain. The non-secret provider registry contains the provider kind,
model ID, endpoint override, and limits, but never the credential. When native
Chat starts its isolated model process, REL supplies the selected key through
private standard input rather than an environment variable or command-line
argument.

For more app configuration, see the [macOS app guide](/app/).
