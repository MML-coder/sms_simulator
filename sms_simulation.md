## SMS Simulation Exercise

Design and implement a scalable SMS alert simulation system

## Requirements

### Components

1. **Producer**

* Generate a configurable number (default 1000) of random SMS messages.
* Each message contains up to 100 random characters.

2. **Senders**

* Configurable number of senders.
* Each sender:
    * Consumes messages from the producer.
    * Simulates sending by waiting a random time (configurable mean).
    * Has a configurable failure rate.

3. **Progress Monitor**

* Displays and updates (every N seconds, configurable):
    * Number of messages sent.
    * Number of messages failed.
    * Average time per message.

## Technical Requirements

- Choose a suitable programming language (e.g. Python, Rust).
- Design for scalability and concurrency.
- Implement a suitable data structure or mechanism for message passing.
- Implement unit testing.
- Provide technical documentation.

## Evaluation Criteria

- System design and architecture.
- Scalability, concurrency, and performance.
- Code quality, maintainability, and testing.
- Technical documentation.

## Submission Guidelines

- Create a new Git repository for your solution.
- Implement required components and test thoroughly.
- Provide technical documentation.
- Make your repository publicly accessible.

## Human-AI Collaboration Guidelines

- Using AI-assisted tools is allowed but not required.
- We are more excited to receive a hand-crafted solution that is complete and correct than to receive an AI-assisted
  solution that is large and expansive in features. We are confident that if you know how to code then you can direct AI
  tools to code solutions but not vice versa.
- If you use AI in your solution, please state what tool and more importantly how you used AI in your solution. Do not
  make us guess.

If you choose to use AI-assisted tools, we recommend the following workflow:

1. Create a new branch.
2. Create an implementation plan:
    1. Human creates a new TODO file or section in an existing file outlining the feature to be added.
    2. Human writes TODO list for the feature.
    3. AI reviews the TODO list and suggests improvements. Human and AI iterate until the TODO list is complete, and
       ambiguities are resolved. Including implementation order.
    4. TODO entries are written and edited exclusively by the human, AI suggests improvements only through the chat
       interface.
3. Human asks AI to implement items on TODO list 1-by-1. AI stops after each item, it does not continue to the next item
   yet.
    1. Human reviews the code, suggests improvements, may hand-code improvements. Human and AI iterate on change until
       the item is complete.
    2. Once human approves of the change, move on the next item on the TODO list. It is advisable, but not required,
       for the human to commit the code before moving on to the next item. This is a judgment call depending on the
       scope of the change.

## Additional Tips

- Consider trade-offs between different implementation approaches.
- Utilize existing libraries and frameworks.
- Demonstrate expertise in system design, concurrency, and performance.