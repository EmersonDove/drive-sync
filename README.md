## How to use
1) Create an oauth app on google cloud console (APIs & Services tab -> Credentials -> Create Credentails (you want it underneath OAuth 2.0 Client IDs). Basically you should end up with a json thats like `client_secret_xxxxxxxxxxxxxxxx(bunch of stuff).apps.googleusercontent.com.json`
2) Script will ask you to open a url, open that url and log in with the account you want. idk how to host a server in go, so when it redirects, the url will look something like
    `http://localhost/?state=state-token&code=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx&scope=https://www.googleapis.com/auth/drive.readonly`
3) Copy everything after `code=` and `&`, so here that's `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4) Paste that into terminal