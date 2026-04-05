package org.example.api.dto;

import java.util.List;

public class PlaylistRequest {
    private List<String> playlist;
    private String userId;

    public List<String> getPlaylist() {
        return playlist;
    }

    public void setPlaylist(List<String> playlist) {
        this.playlist = playlist;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }
}
