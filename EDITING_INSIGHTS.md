# Editing Insights

You can edit insights via the admin interface that Django provides.

## Editing insights on Production (and Staging)

### Using reverse proxy

https://0kuna-adm1n.holi.social/production/admin provides the admin interface for production, https://0kuna-adm1n.holi.social/staging/admin for the staging/main branch.

## Protocol of setting up editing insights

### Creating Superuser in DB

The hop host needed permissions to allow connecting to cloud sql. The following guide shows the needed steps:

https://cloud.google.com/sql/docs/postgres/connect-instance-private-ip#connect

I installed the cloud sql proxy on the hop host and ran it with:

```
./cloud_sql_proxy -instances=holi-shared:europe-north1:developm3nt=tcp:5432
```

I then used port forwarding to tunnel a local connection to the proxy:

```
gcloud compute ssh --zone "europe-north1-a" "hop-host-for-okuna-admin-interface" --project "holi-shared" -- -L 6543:localhost:5432
```

And then I could execute (in the project directory):

```
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@myproject.com', 'password')" | python manage.py shell
```

(from https://stackoverflow.com/questions/6244382/how-to-automate-createsuperuser-on-django)
