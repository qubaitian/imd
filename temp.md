When you chat, reply, docs, code comments, git commits:  
    Use simple English if possible.
    One word one meaning: same term for same thing.  
    One idea per sentence.  
    One sentence per line with two spaces.  
    Follow the format and conventions of each file.  

Check the **glossary** in `README.md`.  
If a term is different or unclear, or has many meanings:  
    Suggest one clear term.  

If the task is clear and no user decision blocks progress:  
    Work.  
Otherwise:  
    Review the relevant docs and code first.  
    Ask only for decisions that block progress.  

In the interview:  
    Build a **design tree**.  
    A **decision** is a choice only I can make.  
    The **frontier** is the set of decisions ready to ask me.  
    Ask questions in rounds.  
    Don't ask what the docs, the code, and the web already define.  
    Make routine implementation choices yourself.  
    Give one recommended answer for each decision.  
    Use this format:  
        Q1. title
        question
        A. choice. cost
        B. choice. cost
        recommend: A. reason
    Wait for my answers.  
    When I answer:  
        Update the design tree.  
        Find the next frontier.  
        Ask the next round.  
    When you can build, and no blocks:  
        Show me the design.  

After the interview:  
    update the **glossary** in `README.md`:  
        Define each term in one sentence.  
        Keep terms from the same area together.  
        Put a term before any term that uses it.  
    Update the **ADR** section in `README.md`:   
        Add an ADR when the choice is surprising without context.  
        A future reader will wonder why we chose it.  
    Work when `README.md` is ok.  

