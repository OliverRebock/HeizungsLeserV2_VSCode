select count(*) as tenants from tenant;
select count(*) as users from "user";
select count(*) as links from user_tenant_link;
select count(*) as devices from device;

select id, email, is_superuser from "user" order by id;
select user_id, tenant_id, role from user_tenant_link order by user_id, tenant_id;
select id, name from tenant order by id;
select id, entity_id, tenant_id, name from device order by id limit 20;
