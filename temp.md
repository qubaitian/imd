When you chat, reply, docs, code comments, git commits:  
    Use simple English if possible.
    One word one meaning: same term for same thing.  
    One idea per sentence.  
    One sentence per line with two spaces.  
    When one sentence uses `when`, `if`, `unless`, or another condition:  
        Indent the next lines by 4 spaces.  
        Write the block like Python.  

Check the **glossary** in `README.md`.  
If a term is different or unclear, or has many meanings:  
    Suggest one clear term.  
    Ask me to confirm that meaning.  

If a work is small and clear:  
    Work.
Else:  
    Start a design interview.  

In the interview:  
    Build a **design tree**.  
    A **decision** is a choice only I can make.  
    The **frontier** is the set of decisions ready to ask me.  
    Ask questions in rounds.  
    Don't ask what the docs, the code, and the web already define.  
    Number each decision.  
    Give one recommended answer for each decision.  
    Use this format:  
        Q1 - title: question and choices
        recommended answer
        ---  
        Q2 - title: question and choices
        recommended answer
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

