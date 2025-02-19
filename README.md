Uses an agent architecture that is largely outdated. For most projects today, I would use the LlamaIndex library, which performs the same functions as this agent architecture but with more sophistication and all the complex logic abstracted away. That said, I'm including this here to showcase the ability and inclination to build tools based on a project's needs.

This agent workflow operates in two steps:

1. **Deliberation**: Without tools, the agent is given the prompt to think through the problem first.
2. **Execution**: With tools, it executes the plan that deliberation came up with.

The architecture is designed to resemble OpenAI's O1 model, which thinks before it acts. There is a Gmail client that I reuse in many projects. My implementation of this has also evolved; I've learned that sending emails directly through the API causes many emails to go to spam because the headers expose these emails as potentially suspicious. Nowadays, I use the client not to send emails directly but to save the emails as drafts and then take advantage of Google Apps Scripts to mass send all drafted emails to the intended recipients. This makes the emails indistinguishable from regular emails while still leveraging the intended functionality.

That said, we still received a decent response rate, allowing my bosses to greenlight the next project—so, small mercies. If you're going to use this, be sure to input your OpenAI API key into the environment variable.

**Weaknesses of the Project:**
- Need to update the file attachment path in both the logic and the prompt.
- If we were to develop this project further, we'd want to refactor so that there's one place where we define the email attachment paths—perhaps by consolidating all the config sections into a singular config file.

As mentioned, this architecture is largely outdated in favor of the LlamaIndex library. Like with most of my projects, I've injected my own personal natural datetime logger. 