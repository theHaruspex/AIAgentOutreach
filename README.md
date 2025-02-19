uses agent architecture that is largely outdated, for most projects today I would just use the llama index library, which does what this agent architecture does except with a bit more sophistication and all the complex logic abstracted away.

that said, I'm including this here to showcase the ability and inclination to build tools based on a project's needs. 

this agent workflow operates in two steps:

1. Deliberation
   1.  w/o tools, the agent is given the prompt to think through the problem first. 
2. Execution
    1. w/ tools, to execute the plan that deliberation came up with

the architecture is meant to resemble open ai's o1 model, which thinks before it acts.





there is the gmail client which I reuse in a lot of projects. my implementation of this has also evoved; I've learned that sending emails simply through the api will cause a lot of emails go to spam, the headers expose these emails as potentially suspicious.

Now adays, I use the client, not to send emails directly, but to save the emails as drafts then take advantage of Google Apps Scripts to mass send all drafted emails to the intended recipients. This leaves it indstinguishable from regular emails while still leveraging the  

That said, we still did get a decent enough response rate for my bosses to greenlight the next project. so, small mercies.


If you're going to use this, be sure to input your openai api key into the environment variable 


weaknessess of the project:
   need to update the file attachment path in the logic, and also in the prompt. if we were developing this project further, we'd want to refactor so that there's one place that we define the email attatchment paths-- maybe refactor all the config sections into a singlular config file-- but as we said, this architecture is largely outdated in favor of the llama-index library.


like with most of my projects, I've inhected my own personal natural datetime logger