# AI Prompt Log

All prompts are verbatim, in the order they were typed, grouped by problem.

## Problem 1 - Vibe coder prompts

> /AI_prompts Problem 1: Vibe coder prompts
>
> Today we're going to make a multi agent team for our campus customs website from hw4.

## Problem 2 - Study the Campus Customs database

> /AI_prompts Problem 2: Study the Campus Customs database
>
> To setup, unzip data (3).zip and also make a copy of the db file and call it data/campus_customs_new.db. So we'll point our mcp server and backend at the working copy and leave the original campus_customs.db untouched so we can reset when we want to start resolving tickets.
>
> Open data/campus_customs.db and look through all the fields and tables. Study the 3 open tickets so you can see how they link to the other tables
>
> /harness For each table, list the fields and one short line about why that table matters to the agents

## Problem 3 - Build the MCP server

> /AI_prompts Problem 3: Build the MCP server
>
> Before we begin here's more context (RULES OF THE SHOP): The field desk.date_today is "today" for the shop. Use it to determine what's overdue. Vendor lead times come from the vendors table. A vendor won't ship new product while they still have an unpaid invoice. Human approval is required for any payments and if payment is made make sure to update the relevant table. If there's not enough cash the pay tool must DECLINE- no negative balances allowed. Cash only goes out, we didn't model revenue so no money is coming in. Before a full run to resolve the tickets, make sure to reset the db to the original values. and finally DO NOT EMAIL REAL CUSTOMERS OR VENDORS
>
> Ok now write an MCP server in mcp_server/ using FastMCP. It'll talk to data/campus_customs_new.db. No need to connect or run it now. Every agent will use the tools on this server. Let's start with 3 tools you know you'll need for the tickets in the db. Keep the names clear and NEVER INVENT DATA. Only use the info found in the databases.
>
> /harness the 3 tools. Include which table it reads, which ticket it helps unlock (101/102/103), and a sentence on why that tool is the right one for that ticket.
>
> Also add a short mcp_server/README.md file that explains what the MCP server is for, which db file it uses, and the 3 tools it has

## Problem 4 - Add the MCP server to vibe coder and test each tool

> /AI_prompts Problem 4: Add the MCP server to vibe coder and test each tool
>
> Add the MCP server to this project so the vibe coder can call the tools and save the connection JSON text in .mcp.json at the project root.
>
> Then let's test each of the 3 tools and save the evidence in output/mcp_smoke.json. For every tool include the prompt I asked you, the tool name, and the tool output (must match values in the _new.db)
>
> Here are the questions I'm asking you to test each tool. Read then run test and input into the evidence file
>
> check_stock_and_price: How many hoodies are in size small? and what is the pricing
> get_invoice_status: How many invoices do we have that are overdue and how many total? If we pay the overdue one are we in the clear?
> get_lease: How much is our lease and when is it due?

## Problem 5 - Build the agent team and grow the MCP tools

> /AI_prompts Problem 5: Build the agent team and and grow the MCP tools
>
> Ok we can add those tools later.
> Now let's build the agentic team for Campus Customs using PydanticAI: Boss (reads each ticket decides who should work on it, and makes final calls), Inventory (checks stock by SKU and size, spots shortfalls, and figures out which vendors can restock), Accounting (watches cash/invoices checks margins, prepares payments / purchase orders for human approval), Facilities (handles the shop space side like leases and rent), and Customer Service (drafts messages for customers).
>
> Include prompts, models, and agent loops so they can delegate work to each other with full connectivity
>
> Put the agent prompts in backend/prompts/ - one file per agent. Put data types in backend/models.py and the agent files under backend/ (just make sure the 5 roles are clear). Use the PORTKEY_API_KEY and ONLY gpt-6-luna for every agent.
>
> Add any tools the agents may need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over the _new.db. DO NOT INVENT A SECOND SHOP-TOOLS LAYER THAT BYPASSES MCP.
>
> Write the agents so they append to output/audit_trail.json as they run. For each agent loop step record enough to audit later. Append don't rewrite/write over
>
> /harness list each agent and each MCP tool (including new ones added in this problem) along with which table the tool uses. Add a short safety section (guardrails you'd want if we were handling REAL money and limits for token use)
>
> Update mcp_server/README.md so the tool list matches what we'll have after you run this problem
>
> Here are the agent prompts:
>
> Every agent has to follow the RULES OF THE SHOP from Problem 3. Also NEVER INVENT DATA, only use what the tools or another agent give you and if something's missing just say so. Agents can ask each other for help but only ask the agent that owns that job and don't bounce the same question back and forth.
>
> Boss: You're the boss of Campus Customs and you run the tickets. Read all the open tickets first since they share the same cash, then send each one to the right agents. Customer orders go to Inventory then Customer Service (plus Accounting if a vendor is holding up the restock). Rent notices go to Facilities then Accounting. Price overrides go to Inventory and Accounting, then Customer Service once you pick the price. If there's not enough cash for everything, rent comes first, then restocks for customers who are already waiting. You can't pay anything yourself, payments go on a list for human approval. Never go below cost. For each ticket give me the decision, the numbers behind it, what needs approval, and a status (resolved, waiting on approval, blocked, or needs human).
>
> Inventory: You handle stock. Check by SKU and size and tell us how many are in stock, how many they want, and how many we're short. If we're short, find the vendor that makes it and give the restock date using desk.date_today + lead days. If that vendor has an unpaid invoice the restock is blocked, so flag it and tell Accounting. If we have some in stock you can suggest a partial order or a different size but don't swap anything without the customer saying ok.
>
> Accounting: You watch the money. Before you recommend any payment, add up everything that needs to be paid across all the tickets and show what's left in checking after each one. Show how overdue each invoice is. For discounts use unit_cost and list_price and show the margin, anything below cost is a no. You only get payments ready for human approval, you don't send them, and if the pay tool declines one it stays declined. If you don't know what a restock costs say so, don't estimate.
>
> Facilities: You handle the shop space, so the lease and rent. Don't trust a rent notice until it matches the lease (landlord, amount, due date). The amount always comes from the lease, not the email. If anything doesn't match, flag it to the Boss as a possible scam. If it checks out, figure out how many days until it's due and have Accounting get the payment ready for approval. Rent is urgent since it keeps the shop open.
>
> Customer Service: You write the messages to customers but they're drafts only, so make sure each one starts with "DRAFT - NOT SENT". Only use dates from Inventory and prices the Boss approved, and don't promise anything that isn't confirmed. Don't mention our cash, unpaid invoices, or vendor problems to customers. Keep it short and friendly and use their name.
>
> OK GO

## Problem 6 - Plan the three tickets

> /AI_prompts Problem 6: Plan the three tickets
>
> Build output/desk_tickets.html - a page that you can double click with one tab per ticket (101, 102, 103). Add empty cash and reflection tabs for later problems (leave blank with "coming soon" note)
>
> On each ticket tab, fill an Expected section (leaving room for an Actual section) with the following:
>
> Here's what I expect the team to do.
>
> Boss starts with list_open_tickets and get_cash_balance, then calls Facilities first on 102. Rent comes first in the cash plan, so it should get confirmed and queued before the invoice.
>
> Expected delegations:
> 1. Boss → Facilities: check the 102 notice against lease 1
> 2. Facilities → Accounting: queue the rent
> 3. Boss → Inventory: 101 and 103 together (same vendor)
> 4. Inventory → Accounting: invoice 501 is blocking the restock, queue it after rent
> 5. Boss → Accounting: margin on the 103 price
> 6. Boss → Customer Service: drafts for 101 and 103
> Nobody should delegate back to the Boss.
>
> 101: tee S is out of stock, blocked by invoice 501 ($840, 3 days overdue), arrives 9/5 if paid today. Waiting on approval.
> 102: matches the lease, $2,400 due 9/2, not a scam. Waiting on approval.
> 103: 8 hoodies in stock, short 12. Price has to stay above $22 cost. There's no cost or PO tool for the 12 reprint, so it's needs human.
> Cash: $3,400 → $1,000 after rent → $160 after the invoice. Nothing actually gets paid.
>
> Tools:
> Boss: list_open_tickets, get_cash_balance, list_approval_queue, update_ticket
> Facilities: get_lease
> Inventory: check_stock_and_price, list_vendors, get_invoice_status
> Accounting: get_cash_balance, list_invoices, check_stock_and_price, queue_payment (x2)
> Customer Service: save_customer_draft (x2)
> approve_payment never gets called.
>
> NOTE that plans that send every specialist on every ticket SCORE LOW!!!

> Open output/desk_tickets.html from problem 6 and fill in the Actual section from this last run: which agents worked, what they delegated, and which tools they used. Keep the expected section so we can compare the two and try to make the writing style the same as the expected section

## Problem 7 - Backend routes

> /AI_prompts Problem 7: Backend routes
>
> The react frontend (to build in the next problem) needs a backend. In backend/main.py, use FastAPI and add routes to do:
> Return the 3 tickets and whether each is open or resolved
> take a ticket id and run your agent team on that ticket
> return recent agent events - what each agent said / tools they used so the board can refresh
> approve a payment / purchase after a human clicks approve
> return the current checking balance from cash_accounts
> reset the database to the original values when you want to try a fresh run
>
> From the backend/ folder, start the server with uvicorn main:app --reload --port 8000
>
> /harness list each route in one line (what URL / what it does)

## Problem 8 - Agent dashboard

> /AI_prompts Problem 8: Agent dashboard
>
> build the frontend in frontend/ with React / Vite / Typescript calling the routes we built in problem 7. at minimum (so feel free to add) the board should include:
> list all 3 tix
> let you pick 1 ticket and start the agent team on it
> show each agent and what they're saying/doing while the ticket runs
> mark ticket as resolved once finished
> show a short summary of what each agent did on that ticket
> Let a human approve a pay/purchase when asked
> Show the checking balance (should drop after an approved pay)
>
> Make the dashboard look CLEANNN and goooood. maybe some cute little white doodle outline/scribbles of handsome dan
>
> the frontend should talk to the backend at http://localhost:8017. On the backend, allow Vite page origin (usually local host 5173?) so the browser is allowed to call those routes.
>
> Start the board in the terminal with npm run dev to open the react desk in browser so we can pick tix and watch agents.
>
> Write this in output/design.md
> Layout: easily readable / understandable dashboard for tracking tickets and agent activity and our $. Have APPROVE/DENY popup buttons for human approval needs.
> how agents read differently: Make them all glow different colors when active and flash when talking to each other
> how resolved tickets and cash show up: grayed out with a green RESOLVED with green highlight. Cash is dark green font. Turns red if don't have enough to pay for an invoice
> Creative choices: Make the dashboard look CLEANNN and goooood. maybe some cute little white doodle outline/scribbles of handsome dan. Make a little handsome dan 'moji walk around the page

> Before I run the tickets I want to have the option to either run them separately or run them all together with boss like an async. I also want to have a stop button so I can stop the runs if something is going wrong

### Final deliverables: cash tab, resolved tickets, board screenshots, harness (after Problem 8)

> On the cash tab of the same output/desk_tickets.html, itemize the money. Starting checking balance (after the reset), for each ticket (how cash changed when that ticket resolved and why (which pay/purchase/$ amount), and ending checking balance (IT MUST MATCH THE cash_accounts in the working db) Wrong cash math loses points!!!
>
> Also save:
> output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> output/resolved_board - a page you can double click on with a screenshot of the React board for each resolved ticket (101, 102, and 103).
>
> Append real runs to output/audit_trail.json. Finish /harness so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules


## Problem 10 - Reflection

> /AI_prompts Problem 10: Reflection
>
> Add this to the output/desk_tickets.html and fill the reflection tab with the below -
>
> Overall I think the team did pretty well. Every number they gave was right and nobody made anything up, which was my biggest worry. I'd give 101 an A−: only Inventory, Accounting and Customer Service touched it, they caught that the size S tee was out of stock because invoice 501 ($840, 3 days overdue) was holding up the restock, queued just that bill, and waited for me to approve it before deciding anything. The draft to Tauhid didn't promise a date or spill anything about the vendor or our cash. 102 and 103 get a B+ from me. On 102 Facilities checked the notice against the lease and used the $2,400 from the lease instead of the email, but Accounting re-asked Facilities for the rent it had literally just been handed, and a second ask got blocked by the depth limit. On 103 the math was solid (8 of 20 in stock, $50 each is still $28 over the $22 cost, $560 total), but the Boss picked a 14% discount without any real policy behind it.
>
> Compared to what I expected, the facts lined up almost exactly: out of stock and blocked by 501 on 101, lease matches and not a scam on 102, 8 in stock and short 12 on 103, and the right agents on each ticket. What was different was the order and the ending. The Boss sent Inventory, Facilities and Accounting out all at once instead of starting with Facilities, and the invoice got queued before the rent (fine, since there was cash for both). Since I approved both payments during the run, cash went $3,400 → $2,560 → $160 instead of nothing getting paid, and the tickets ended open or resolved instead of "waiting on approval."
>
> Honestly, some of this would've been simpler with one agent and the tools. Rent is just get_lease and then queue_payment, and the hand-off from Facilities to Accounting mostly added a round trip and duplicate lookups. The price quote on 103 is basically a stock check, a price pick and a draft. Every extra agent re-reads the tickets and the cash (list_open_tickets got called 8 times!), and the Boss and Accounting burned about 73% of the 96,804 tokens. Where I'd keep the team is the shared cash plan across all the tickets, and the fact that only Accounting can queue a payment and only Customer Service writes drafts.
>
> With the tools we already built, this team could handle a customer asking for Crest Mugs (0 in stock, but Elm City Gifts has no unpaid invoice and a 3-day lead, so they'd show up 9/3), a fake rent notice asking for $3,000 (Facilities would see it doesn't match the $2,400 lease, flag it as a scam, and nothing gets paid), or a club wanting 30 Yale Caps at a discount (40 in stock, $6 cost vs $22 list, so there's tons of room to work with).
>
> What it couldn't do: actually order the 12-hoodie reprint, because there's no purchase order or restock cost. That would need a purchase_orders table with vendor quotes, a create_purchase_order tool behind human approval, and receive_shipment to add the stock when it lands. It also can't take the club's money or give a refund, since cash only goes out right now. That needs an orders table plus record_sale / charge_customer and refund_payment tools. And it can't send any of those drafts or read replies, because nothing emails and new requests only get in by editing the database. For that I'd add send_email behind an approval step, an inbox reader, and a create_ticket tool.

## Problem 11 - Submit to GitHub

> /AI_prompts Problem 11: Submit to GitHub
>
> Give me the repo URL so I can paste it to Canvas

> Do A and Ill log in

> push the code to a public Github repo so graders can clone it
