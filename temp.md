Before you work:  
    Interview me until we share one understanding.  

During the interview:  
    Make a **design tree**:
        Each decision branches into the decisions that depend on it.  
        Make the tree in **rounds**.  
        The **frontier** is every decision with settled prerequisites.  
        Use only answers that I give.  
        Ask the frontier in one round.  
        Number each **question**.  
        Use this **question** format:  
            ```
            **Q1** - **<question title>**: <question body. Add choices if needed.>
            <your recommended answer>
            -----
            **Q2** - **<question title>**: <question body. Add choices if needed.>
            <your recommended answer>
            ```
        Give your recommended answer.  
        Wait for my answers before the next round.  
        When I answer:  
            Change the **design tree**.  
        Settled decisions move the frontier out.  
        Those decisions open the questions that waited on them.  
        Compute the frontier again.  
        Ask the next round.  
        When a question needs an answer that is still open in this round:  
            Put that question in a later round.  
        Find **facts** yourself.  
        Ask me only for a decision.  
        Ask the rest of the frontier now.  
        I make the decision.  
        You wait.  
        The interview is complete when the frontier is empty.  
        Every branch of the design tree is visited.  
        Every decision comes from me.  
    Update each **term** in `README.md`:
        When I use a word that does not match `README.md`:  
            Ask which meaning is right at once.  
            Example:  
                Your term says 'cancellation' means X.  
                You seem to mean Y.  
                Which one is right?  
        When I use a word with many meanings:  
            Offer one clear word.  
            Example:  
                You say 'account'.  
                Do you mean the Customer or the User?  
                They are different.  
        Follow the **term** rules.  
        When many words name the same idea:  
            Pick the best word.  
            List the other words under `_Avoid_`.  
        Keep each definition short.  
        Use one or two sentences.  
        Say what the term is.  
        Leave out what the term does.  
        Add a term only when it is special to this project.  
        Leave out a general programming word.  
        Group terms that belong together.  
        Put a term before the terms that depend on it.  
    Update each **ADR** in `README.md`: 
        An **ADR** is an Architecture Decision Record.  
        A future reader looks at the code and asks why it works this way.  
        You pick one option for a clear reason.  
        A future reader asks why you picked it.  
        When I say how something works:  
            Check if the code matches.  
            Raise the conflict at once.  
            Example:  
                Your code cancels the whole Order.  
                You just said a partial cancel is possible.  
                Which one is right?  
    Do these steps until I confirm one shared understanding.  
