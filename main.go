package main

import (
	"context"
	"encoding/json"
	"fmt"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/drive/v3"
	"io/ioutil"
	"log"
	"net/http"
	"os"
)

func main() {
	// Read the credentials file
	b, err := ioutil.ReadFile("./client_secret_258328592002-0pi6f03umgaj61h1qlr3a17fav53grno.apps.googleusercontent.com.json")
	if err != nil {
		log.Fatalf("Unable to read client secret file: %v", err)
	}

	// Create the config from the credentials file
	config, err := google.ConfigFromJSON(b, drive.DriveReadonlyScope)
	if err != nil {
		log.Fatalf("Unable to parse client config: %v", err)
	}

	// Retrieve a token, saves the token, then returns the generated client
	client := getClient(config)

	srv, err := drive.New(client)
	if err != nil {
		log.Fatalf("Unable to retrieve Drive client: %v", err)
	}

	fmt.Println("Listing files and folders:")
	listAllFiles(srv, "root", "")
}

func listAllFiles(srv *drive.Service, folderID string, indent string) {
	// Fetch files and folders within the current folderID
	r, err := srv.Files.List().
		Q(fmt.Sprintf("'%s' in parents", folderID)).
		Fields("nextPageToken, files(id, name, mimeType)").
		Do()
	if err != nil {
		log.Fatalf("Unable to retrieve files: %v", err)
	}

	// Print each file and folder
	for _, i := range r.Files {
		if i.MimeType == "application/vnd.google-apps.folder" {
			// If it's a folder, print its name and recurse into it
			fmt.Printf("%s[Folder] %s\n", indent, i.Name)
			listAllFiles(srv, i.Id, indent+"--")
		} else {
			// If it's a file, print its name
			fmt.Printf("%s[File] %s\n", indent, i.Name)
		}
	}

	// Handle pagination (if there are more files to fetch)
	for r.NextPageToken != "" {
		r, err = srv.Files.List().
			Q(fmt.Sprintf("'%s' in parents", folderID)).
			PageToken(r.NextPageToken).
			Fields("nextPageToken, files(id, name, mimeType)").
			Do()
		if err != nil {
			log.Fatalf("Unable to retrieve files on next page: %v", err)
		}

		for _, i := range r.Files {
			if i.MimeType == "application/vnd.google-apps.folder" {
				fmt.Printf("%s[Folder] %s\n", indent, i.Name)
				listAllFiles(srv, i.Id, indent+"--")
			} else {
				fmt.Printf("%s[File] %s\n", indent, i.Name)
			}
		}
	}
}

func getClient(config *oauth2.Config) *http.Client {
	tokFile := "token.json"
	tok, err := tokenFromFile(tokFile)
	if err != nil {
		tok = getTokenFromWeb(config)
		saveToken(tokFile, tok)
	}
	return config.Client(context.Background(), tok)
}

func getTokenFromWeb(config *oauth2.Config) *oauth2.Token {
	authURL := config.AuthCodeURL("state-token", oauth2.AccessTypeOffline)
	fmt.Printf("Go to the following link in your browser then type the "+
		"authorization code: \n%v\n", authURL)

	var authCode string
	if _, err := fmt.Scan(&authCode); err != nil {
		log.Fatalf("Unable to read authorization code: %v", err)
	}

	tok, err := config.Exchange(context.TODO(), authCode)
	if err != nil {
		log.Fatalf("Unable to retrieve token from web: %v", err)
	}
	return tok
}

func tokenFromFile(file string) (*oauth2.Token, error) {
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	tok := &oauth2.Token{}
	err = json.NewDecoder(f).Decode(tok)
	return tok, err
}

func saveToken(path string, token *oauth2.Token) {
	fmt.Printf("Saving credential file to: %s\n", path)
	f, err := os.Create(path)
	if err != nil {
		log.Fatalf("Unable to cache oauth token: %v", err)
	}
	defer f.Close()
	json.NewEncoder(f).Encode(token)
}
