//
//  MediaHeadlineView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import SwiftUI

struct MediaHeadlineView: View {
    let news: News
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(news.sourceMedium.pressMedia.name.normalized())
                .resizable()
                .scaledToFit()
                .frame(height: 20)
            
            Text(news.title)
                .font(.title3)
                .fontWeight(.semibold)
            
            Spacer()
            
            BiasScoreView()
        }
        .padding()  
        .frame(width: 220, height: 220)
        .background(.regularMaterial)
        .clipShape(.rect(cornerRadius: 20))
    }
}

#Preview {
    MediaHeadlineView(news: .mock)
}
