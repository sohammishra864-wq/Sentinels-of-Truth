-- claims : the facts database
create table if not exists claims(
    claim_id integer primary key autoincrement , claim_text text not null, verdict text check(verdict in ('REAL', 'FAKE', 'UNCERTAIN')),confidence real check(confidence >= 0 and confidence <= 1), sources text , created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp
);
-- conflicts : keeps track of the conflicts
create table if not exists conflicts(
    conflict_id integer primary key autoincrement , new_claim_text text not null , existing_claim_id integer references claims(claim_id), status text default 'PENDING' check(status in ('PENDING', 'RESOLVED', 'FLAGGED')), created_at timestamp default current_timestamp ,
    updated_at timestamp default current_timestamp

);
-- verification_history : its for just history
create table if not exists verification_history(
    history_id integer primary key autoincrement , claim_text text not null , agent_action text , final_action text check(final_action in ('INSERT', 'FLAG', 'DISCARD','PENDING')), timeestanmp timestamp default current_timestamp
);