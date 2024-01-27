package main

import (
	"context"
	"encoding/json"
	"fmt"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/drive/v3"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
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
	initialLocalPath := "/Volumes/Google Drive Backup/edove@vt.edu-01:27:24" // Or any path you prefer
	// Make this directory
	os.MkdirAll(initialLocalPath, os.ModePerm)
	listAllFiles(srv, "root", "", initialLocalPath)
}

func listAllFiles(srv *drive.Service, folderID, indent, localPath string) { // Fetch files and folders within the current folderID
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
			// Create local directory
			newLocalPath := filepath.Join(localPath, i.Name)
			os.MkdirAll(newLocalPath, os.ModePerm)

			fmt.Printf("%s[Folder] %s\n", indent, i.Name)
			listAllFiles(srv, i.Id, indent+"--", newLocalPath)
		} else {
			// Download the file
			filePath := filepath.Join(localPath, i.Name)
			fmt.Printf("%s[Downloading file] %s\n", indent, i.Name)
			downloadFile(srv, i.Id, filePath)
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
				listAllFiles(srv, i.Id, indent+"--", localPath)
			} else {
				fmt.Printf("%s[File] %s\n", indent, i.Name)
			}
		}
	}
}

func downloadFile(srv *drive.Service, fileID, filePath string) {
	tempFilePath := filePath + ".temp"

	// Check if the final file already exists, if it does just return
	if _, err := os.Stat(filePath); err == nil {
		fmt.Printf("File %s already exists, skipping download\n", filePath)
		return
	}

	// Delete any existing temp file from previous failed downloads
	if _, err := os.Stat(tempFilePath); err == nil {
		if err := os.Remove(tempFilePath); err != nil {
			log.Fatalf("Unable to delete existing temp file: %v", err)
		}
	}

	// Get the file type
	file, err := srv.Files.Get(fileID).Fields("mimeType").Do()
	if err != nil {
		log.Printf("Unable to get file: %v", err)
		appendFailedDownload(filePath)
		return
	}

	// Declare a reader for file content
	var content io.ReadCloser
	var isGoogleDocType bool

	// Check if the file is a Google Doc type and export it, otherwise download it
	if strings.HasPrefix(file.MimeType, "application/vnd.google-apps.") {
		// It's a Google Doc type, export as PDF
		resp, err := srv.Files.Export(fileID, "application/pdf").Download()
		if err != nil {
			log.Printf("Unable to export file: %v", err)
			appendFailedDownload(filePath)
			return
		}
		content = resp.Body
		tempFilePath += ".pdf" // Add PDF extension to temp file
		isGoogleDocType = true
	} else {
		// It's a downloadable file
		resp, err := srv.Files.Get(fileID).Download()
		if err != nil {
			log.Printf("Unable to download file: %v", err)
			appendFailedDownload(filePath)
			return
		}
		content = resp.Body
	}
	defer content.Close()

	// Create a temp file
	fmt.Printf("Writing file %s\n", tempFilePath)
	f, err := os.Create(tempFilePath)
	if err != nil {
		log.Printf("Unable to create temp file: %v", err)
		appendFailedDownload(filePath)
		return
	}
	defer f.Close()

	// Copy the contents to the temp file
	_, err = io.Copy(f, content)
	if err != nil {
		log.Printf("Unable to write to temp file: %v", err)
		appendFailedDownload(filePath)
		return
	}

	// Rename the temp file to the final file name
	finalFilePath := filePath
	if isGoogleDocType {
		finalFilePath += ".pdf" // Add .pdf extension for Google Doc types
	}
	if err := os.Rename(tempFilePath, finalFilePath); err != nil {
		log.Printf("Unable to rename temp file to final file: %v", err)
		appendFailedDownload(filePath)
	}
}

// appendFailedDownload logs the failed download path to a text file
func appendFailedDownload(filePath string) {
	f, err := os.OpenFile("failed_downloads.txt", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("Unable to open failed downloads log file: %v", err)
		return
	}
	defer f.Close()

	if _, err := f.WriteString(filePath + "\n"); err != nil {
		log.Printf("Unable to write to failed downloads log file: %v", err)
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
