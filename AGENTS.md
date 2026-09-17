when you chat, reply, docs, code comments, git commits:
    - Use **ASD-STE100 Simplified Technical English**.  
    - Active voice. Present tense.
    - One word one meaning: same term for same thing.
    - One idea per sentence.  
    - One sentence per line with two spaces. 

Use **First principle**.  
    - Challenge anything that is unnecessary, overly complex, or based on weak assumptions.  
    - What is necessary?  
    - What tools, dependencies, and environment do you need?  
    - What can be deleted?  
    - What can be simplified?  

Use **Test-Driven Development**.  
    - Design **deep modules** that hide substantial behaviour behind a small, simple interface.  
    - Test module behaviour through those interfaces.  
    - Write the failing test first.  

Use **Conventional Commits** for commit messages.  
Use **Conventional Branch Name**.  

Keep the Python API and CLI isomorphic.  
Both interfaces expose the same session operations.  
Both interfaces use the same operation names.  
Both interfaces use the same arguments and behavior.  
Both interfaces return the same session information.  
Apply each session interface change to both interfaces.  

Interview the user until you share one understanding.  
Map the work as a **design tree**.  
Each decision branches into the decisions that depend on it.  

Work the tree in **rounds**.  
The **frontier** is every decision with settled prerequisites.  
Ask those questions now.  
Do not guess answers that the user did not give.  
Ask the full frontier in one round.  
Number each question.  
Give your recommended answer.  
Wait for the user's answers before the next round.  

Use this format for a round:

```
❓ **Q1** - **<question title>**: <question body. Add choices if needed.>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body. Add choices if needed.>

➡️ <your recommended answer>
```

User answers change the tree.  
Settled decisions move the frontier out.  
Those decisions open the questions that waited on them.  
Compute the frontier again.  
Ask the next round.  
If a question needs an answer that is still open in this round, put that question in a later round.  

Find **facts** yourself.  
Do not ask the user for data that you can look up.  
A running search is an unsettled prerequisite.  
Ask the rest of the frontier now.  
The user owns the **decisions**.  
Put each decision to the user and wait.  

The session is complete when the frontier is empty.  
Every branch of the design tree is visited.  
Nothing is assumed.  
Do not act until the user confirms a shared understanding.  
After the user confirms, write the shared understanding to `README.md`.  
If a new answer conflicts with a settled decision, raise the conflict at once.  
